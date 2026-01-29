import asyncio
import os
import re
import shutil
from asyncio import Semaphore
from app.core.celery_app import celery_app
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.subscription import Subscription
from app.models.sync_state import SyncState, SyncStatus, SyncType
from app.models.selection import SelectedCategory
from app.models.cache import MovieCache, SeriesCache, EpisodeCache
from app.models.schedule import Schedule, SyncType as ScheduleSyncType
from app.models.schedule_execution import ScheduleExecution, ExecutionStatus
from app.services.xtream import XtreamClient
from app.services.file_manager import FileManager
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def update_sync_progress(db: Session, subscription_id: int, sync_type: str, current: int, total: int, phase: str):
    """Update sync progress in database"""
    sync_state = db.query(SyncState).filter(
        SyncState.subscription_id == subscription_id,
        SyncState.type == sync_type
    ).first()
    if sync_state:
        sync_state.progress_current = current
        sync_state.progress_total = total
        sync_state.progress_phase = phase
        db.commit()


async def fetch_vod_details_batch(xc: XtreamClient, movies: list, batch_size: int = 10,
                                   db: Session = None, subscription_id: int = None):
    """Fetch VOD details for multiple movies in parallel with concurrency limit"""
    semaphore = Semaphore(batch_size)
    total = len(movies)
    completed = [0]  # Use list for mutable counter in closure

    async def fetch_one(movie):
        async with semaphore:
            stream_id = str(movie['stream_id'])
            try:
                detailed_info = await xc.get_vod_info(stream_id)
                if detailed_info and 'info' in detailed_info:
                    info = detailed_info['info']
                    # Merge video/audio/metadata into movie dict
                    if info.get('video'):
                        movie['video'] = info['video']
                    if info.get('audio'):
                        movie['audio'] = info['audio']
                    if info.get('bitrate'):
                        movie['bitrate'] = info['bitrate']
                    if info.get('duration_secs'):
                        movie['duration_secs'] = info['duration_secs']
                    # Additional metadata
                    if info.get('plot') and not movie.get('plot'):
                        movie['plot'] = info['plot']
                    if info.get('cast') and not movie.get('cast'):
                        movie['cast'] = info['cast']
                    if info.get('director') and not movie.get('director'):
                        movie['director'] = info['director']
                    if info.get('genre') and not movie.get('genre'):
                        movie['genre'] = info['genre']
                    if info.get('release_date') and not movie.get('releasedate'):
                        movie['releasedate'] = info['release_date']
                    if info.get('tmdb_id') and not movie.get('tmdb'):
                        movie['tmdb'] = info['tmdb_id']
            except Exception as e:
                logger.warning(f"Failed to fetch details for movie {stream_id}: {e}")

            completed[0] += 1
            if completed[0] % 100 == 0 or completed[0] == total:
                logger.info(f"Fetched VOD details: {completed[0]}/{total}")
                # Update progress in database
                if db and subscription_id:
                    update_sync_progress(db, subscription_id, SyncType.MOVIES, completed[0], total, "Fetching VOD details")

        return movie

    tasks = [fetch_one(movie) for movie in movies]
    return await asyncio.gather(*tasks)

async def process_movies(db: Session, xc: XtreamClient, fm: FileManager, subscription_id: int):
    # Get settings
    from app.models.settings import SettingsModel
    settings = {s.key: s.value for s in db.query(SettingsModel).all()}
    prefix_regex = settings.get("PREFIX_REGEX")
    format_date = settings.get("FORMAT_DATE_IN_TITLE") == "true"
    clean_name = settings.get("CLEAN_NAME") == "true"

    # Update status
    sync_state = db.query(SyncState).filter(
        SyncState.subscription_id == subscription_id,
        SyncState.type == SyncType.MOVIES
    ).first()
    
    if not sync_state:
        sync_state = SyncState(subscription_id=subscription_id, type=SyncType.MOVIES)
        db.add(sync_state)
    
    sync_state.status = SyncStatus.RUNNING
    sync_state.last_sync = datetime.utcnow()
    db.commit()

    try:
        # Fetch Categories
        categories = await xc.get_vod_categories()
        cat_map = {c['category_id']: c['category_name'] for c in categories}

        # Fetch All Movies
        all_movies = await xc.get_vod_streams()

        # Filter by selected categories if any
        selected_cats = db.query(SelectedCategory).filter(
            SelectedCategory.subscription_id == subscription_id,
            SelectedCategory.type == "movie"
        ).all()
        
        if selected_cats:
            selected_ids = {s.category_id for s in selected_cats}
            all_movies = [m for m in all_movies if m['category_id'] in selected_ids]
        
        # Current Cache
        cached_movies = {m.stream_id: m for m in db.query(MovieCache).filter(MovieCache.subscription_id == subscription_id).all()}
        
        to_add_update = []
        to_delete = []
        
        current_ids = set()

        for movie in all_movies:
            stream_id = int(movie['stream_id'])
            current_ids.add(stream_id)
            
            # Check if changed
            cached = cached_movies.get(stream_id)
            if not cached:
                to_add_update.append(movie)
            else:
                if (cached.name != movie['name'] or
                        cached.container_extension != movie['container_extension'] or
                        cached.tmdb_id != str(movie.get('tmdb', '') or '')):
                    to_add_update.append(movie)

        # Detect deletions
        for stream_id, cached in cached_movies.items():
            if stream_id not in current_ids:
                to_delete.append(cached)

        # Process Deletions
        for movie in to_delete:
            cat_name = cat_map.get(movie.category_id, "Uncategorized")
            safe_cat = fm.sanitize_name(cat_name)
            safe_name = fm.sanitize_name(movie.name)
            tmdb_suffix = fm.format_tmdb_suffix(movie.tmdb_id)

            if tmdb_suffix:
                # Folder-based: {cat}/{name} {tmdb-XXX}/
                folder_path = f"{fm.output_dir}/{safe_cat}/{safe_name}{tmdb_suffix}"
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
            else:
                # Flat: {cat}/{name}.strm
                await fm.delete_file(f"{fm.output_dir}/{safe_cat}/{safe_name}.strm")
                await fm.delete_file(f"{fm.output_dir}/{safe_cat}/{safe_name}.nfo")

            await fm.delete_directory_if_empty(f"{fm.output_dir}/{safe_cat}")
            db.delete(movie)
        
        # Fetch VOD details in parallel (10 concurrent requests)
        if to_add_update:
            logger.info(f"Fetching detailed VOD info for {len(to_add_update)} movies (parallel)...")
            update_sync_progress(db, subscription_id, SyncType.MOVIES, 0, len(to_add_update), "Fetching VOD details")
            await fetch_vod_details_batch(xc, to_add_update, batch_size=10, db=db, subscription_id=subscription_id)

        # Process Additions/Updates (now with enriched data)
        total_files = len(to_add_update)
        for idx, movie in enumerate(to_add_update):
            if idx % 100 == 0 or idx == total_files - 1:
                update_sync_progress(db, subscription_id, SyncType.MOVIES, idx + 1, total_files, "Creating files")
            stream_id = int(movie['stream_id'])
            name = movie['name']
            ext = movie['container_extension']
            cat_id = movie['category_id']
            tmdb_id = movie.get('tmdb')  # Xtream API uses 'tmdb' not 'tmdb_id'

            cat_name = cat_map.get(cat_id, "Uncategorized")
            safe_cat = fm.sanitize_name(cat_name)
            safe_name = fm.sanitize_name(name)
            tmdb_suffix = fm.format_tmdb_suffix(tmdb_id)

            cat_dir = f"{fm.output_dir}/{safe_cat}"
            fm.ensure_directory(cat_dir)

            if tmdb_suffix:
                # Per-movie folder with TMDB ID
                movie_dir = f"{cat_dir}/{safe_name}{tmdb_suffix}"
                fm.ensure_directory(movie_dir)
                display_name = f"{safe_name}{tmdb_suffix}"
                strm_path = f"{movie_dir}/{display_name}.strm"
                nfo_path = f"{movie_dir}/{display_name}.nfo"
            else:
                # Flat structure (no valid TMDB)
                strm_path = f"{cat_dir}/{safe_name}.strm"
                nfo_path = f"{cat_dir}/{safe_name}.nfo"

            url = xc.get_stream_url("movie", str(stream_id), ext)
            await fm.write_strm(strm_path, url)

            # Always create NFO file with all available metadata
            nfo_content = fm.generate_movie_nfo(movie, prefix_regex, format_date, clean_name)
            await fm.write_nfo(nfo_path, nfo_content)

            # Clean up old path if TMDB ID changed
            cached = cached_movies.get(stream_id)
            if cached and cached.tmdb_id != (str(tmdb_id) if tmdb_id else None):
                old_suffix = fm.format_tmdb_suffix(cached.tmdb_id)
                if old_suffix:
                    old_path = f"{cat_dir}/{safe_name}{old_suffix}"
                    if os.path.exists(old_path):
                        shutil.rmtree(old_path)
                else:
                    await fm.delete_file(f"{cat_dir}/{safe_name}.strm")
                    await fm.delete_file(f"{cat_dir}/{safe_name}.nfo")

            # Update Cache
            cached = cached_movies.get(stream_id)
            if not cached:
                cached = MovieCache(subscription_id=subscription_id, stream_id=stream_id)
                db.add(cached)
            
            cached.name = name
            cached.category_id = cat_id
            cached.container_extension = ext
            cached.tmdb_id = str(tmdb_id) if tmdb_id else None

        # Check for missing NFO files
        logger.info(f"Checking for missing NFO files across {len(all_movies)} movies...")
        nfo_created_count = 0
        for movie in all_movies:
            stream_id = int(movie['stream_id'])
            name = movie['name']
            cat_id = movie['category_id']
            tmdb_id = movie.get('tmdb')

            cat_name = cat_map.get(cat_id, "Uncategorized")
            safe_cat = fm.sanitize_name(cat_name)
            safe_name = fm.sanitize_name(name)
            tmdb_suffix = fm.format_tmdb_suffix(tmdb_id)

            if tmdb_suffix:
                nfo_path = f"{fm.output_dir}/{safe_cat}/{safe_name}{tmdb_suffix}/{safe_name}{tmdb_suffix}.nfo"
            else:
                nfo_path = f"{fm.output_dir}/{safe_cat}/{safe_name}.nfo"

            if not os.path.exists(nfo_path):
                if tmdb_suffix:
                    fm.ensure_directory(f"{fm.output_dir}/{safe_cat}/{safe_name}{tmdb_suffix}")
                else:
                    fm.ensure_directory(f"{fm.output_dir}/{safe_cat}")
                nfo_content = fm.generate_movie_nfo(movie, prefix_regex, format_date, clean_name)
                await fm.write_nfo(nfo_path, nfo_content)
                nfo_created_count += 1
        
        if nfo_created_count > 0:
            logger.info(f"Created {nfo_created_count} missing NFO files")

        sync_state.items_added = len(to_add_update)
        sync_state.items_deleted = len(to_delete)
        sync_state.status = SyncStatus.SUCCESS
        sync_state.progress_current = 0
        sync_state.progress_total = 0
        sync_state.progress_phase = None
        db.commit()

    except Exception as e:
        logger.exception("Error syncing movies")
        sync_state.status = SyncStatus.FAILED
        sync_state.error_message = str(e)
        sync_state.progress_current = 0
        sync_state.progress_total = 0
        sync_state.progress_phase = None
        db.commit()
        raise

async def process_series(db: Session, xc: XtreamClient, fm: FileManager, subscription_id: int):
    # Get settings
    from app.models.settings import SettingsModel
    settings = {s.key: s.value for s in db.query(SettingsModel).all()}
    prefix_regex = settings.get("PREFIX_REGEX")
    format_date = settings.get("FORMAT_DATE_IN_TITLE") == "true"
    clean_name = settings.get("CLEAN_NAME") == "true"
    # Series format settings (defaults: season folders=true, series name in filename=false)
    use_season_folders = settings.get("SERIES_USE_SEASON_FOLDERS", "true") != "false"
    include_series_name = settings.get("SERIES_INCLUDE_NAME_IN_FILENAME", "false") == "true"

    # Update status
    sync_state = db.query(SyncState).filter(
        SyncState.subscription_id == subscription_id,
        SyncState.type == SyncType.SERIES
    ).first()
    
    if not sync_state:
        sync_state = SyncState(subscription_id=subscription_id, type=SyncType.SERIES)
        db.add(sync_state)
    
    sync_state.status = SyncStatus.RUNNING
    sync_state.last_sync = datetime.utcnow()
    db.commit()

    try:
        categories = await xc.get_series_categories()
        cat_map = {c['category_id']: c['category_name'] for c in categories}

        all_series = await xc.get_series()

        # Filter by selected categories if any
        selected_cats = db.query(SelectedCategory).filter(
            SelectedCategory.subscription_id == subscription_id,
            SelectedCategory.type == "series"
        ).all()
        
        if selected_cats:
            selected_ids = {s.category_id for s in selected_cats}
            all_series = [s for s in all_series if s['category_id'] in selected_ids]
        
        cached_series = {s.series_id: s for s in db.query(SeriesCache).filter(SeriesCache.subscription_id == subscription_id).all()}
        
        to_add_update = []
        to_delete = []
        current_ids = set()

        for series in all_series:
            series_id = int(series['series_id'])
            current_ids.add(series_id)
            
            cached = cached_series.get(series_id)
            if not cached:
                to_add_update.append(series)
            else:
                if (cached.name != series['name'] or
                        cached.tmdb_id != str(series.get('tmdb', '') or '')):
                    to_add_update.append(series)

        for series_id, cached in cached_series.items():
            if series_id not in current_ids:
                to_delete.append(cached)

        # Deletions
        for series in to_delete:
            cat_name = cat_map.get(series.category_id, "Uncategorized")
            safe_cat = fm.sanitize_name(cat_name)
            safe_name = fm.sanitize_name(series.name)
            tmdb_suffix = fm.format_tmdb_suffix(series.tmdb_id)

            path = f"{fm.output_dir}/{safe_cat}/{safe_name}{tmdb_suffix}"
            if os.path.exists(path):
                shutil.rmtree(path)

            await fm.delete_directory_if_empty(f"{fm.output_dir}/{safe_cat}")
            db.delete(series)

        # Additions/Updates
        total_series = len(to_add_update)
        for idx, series in enumerate(to_add_update):
            if idx % 10 == 0 or idx == total_series - 1:
                update_sync_progress(db, subscription_id, SyncType.SERIES, idx + 1, total_series, "Processing series")
            series_id = int(series['series_id'])
            name = series['name']
            cat_id = series['category_id']
            tmdb_id = series.get('tmdb')  # Xtream API uses 'tmdb' not 'tmdb_id'

            cat_name = cat_map.get(cat_id, "Uncategorized")
            safe_cat = fm.sanitize_name(cat_name)
            safe_name = fm.sanitize_name(name)
            tmdb_suffix = fm.format_tmdb_suffix(tmdb_id)

            series_dir = f"{fm.output_dir}/{safe_cat}/{safe_name}{tmdb_suffix}"
            fm.ensure_directory(series_dir)

            # Clean up old folder if TMDB ID changed
            cached = cached_series.get(series_id)
            if cached and cached.tmdb_id != (str(tmdb_id) if tmdb_id else None):
                old_suffix = fm.format_tmdb_suffix(cached.tmdb_id)
                old_name = fm.sanitize_name(cached.name)
                old_path = f"{fm.output_dir}/{safe_cat}/{old_name}{old_suffix}"
                if os.path.exists(old_path) and old_path != series_dir:
                    shutil.rmtree(old_path)

            # Fetch Episodes and Info
            info_response = await xc.get_series_info(str(series_id))
            series_info = info_response.get('info', {})
            episodes_data = info_response.get('episodes', {})
            
            # Fix: Handle case where API returns empty list [] instead of dict {}
            if isinstance(episodes_data, list):
                episodes_data = {}
            
            # PERFORMANCE: Use TMDB ID from get_series() list instead
            # The series dict already has metadata from the list call
            # if series_info.get('tmdb_id'):
            #     series['tmdb_id'] = series_info['tmdb_id']
            #     tmdb_id = series_info['tmdb_id']

            # Always create tvshow.nfo
            nfo_path = f"{series_dir}/tvshow.nfo"
            await fm.write_nfo(nfo_path, fm.generate_show_nfo(series, prefix_regex, format_date, clean_name))
            
            for season_key, episodes in episodes_data.items():
                season_num = int(season_key)

                # Determine episode directory based on settings
                if use_season_folders:
                    # Use zero-padded season numbers for Jellyfin compatibility (Season 01, not Season 1)
                    episode_dir = f"{series_dir}/Season {season_num:02d}"
                    fm.ensure_directory(episode_dir)
                else:
                    episode_dir = series_dir

                for ep in episodes:
                    ep_num = int(ep['episode_num'])
                    ep_id = ep['id']
                    container = ep['container_extension']
                    title = ep.get('title', '')

                    # Build filename based on settings
                    formatted_ep = f"S{season_num:02d}E{ep_num:02d}"

                    # Clean title: remove series name prefix and episode code if present
                    clean_title = title
                    if clean_title:
                        # Remove series name prefix (case-insensitive)
                        if clean_title.lower().startswith(name.lower()):
                            clean_title = clean_title[len(name):].strip(' -:')
                        # Remove episode code patterns like "S01E01 -" or "S01E01"
                        clean_title = re.sub(r'^S\d{1,2}E\d{1,2}\s*[-:.]?\s*', '', clean_title, flags=re.IGNORECASE)
                        # Also handle "1x01" format
                        clean_title = re.sub(r'^\d{1,2}x\d{1,2}\s*[-:.]?\s*', '', clean_title, flags=re.IGNORECASE)
                        clean_title = clean_title.strip(' -:')

                    if include_series_name:
                        # Jellyfin format: Show Name - S01E01 - Episode Title.strm
                        if clean_title:
                            safe_title = fm.sanitize_name(clean_title)
                            filename = f"{safe_name} - {formatted_ep} - {safe_title}"
                        else:
                            filename = f"{safe_name} - {formatted_ep}"
                    else:
                        # Default: S01E01 - Episode Title.strm
                        if clean_title:
                            safe_title = fm.sanitize_name(clean_title)
                            filename = f"{formatted_ep} - {safe_title}"
                        else:
                            filename = formatted_ep

                    strm_path = f"{episode_dir}/{filename}.strm"
                    url = xc.get_stream_url("series", str(ep_id), container)
                    await fm.write_strm(strm_path, url)

                    # Generate episode NFO
                    nfo_path = f"{episode_dir}/{filename}.nfo"
                    await fm.write_nfo(nfo_path, fm.generate_episode_nfo(
                        ep, name, season_num, ep_num, prefix_regex, format_date, clean_name
                    ))

            # Update Cache
            cached = cached_series.get(series_id)
            if not cached:
                cached = SeriesCache(subscription_id=subscription_id, series_id=series_id)
                db.add(cached)
            
            cached.name = name
            cached.category_id = cat_id
            cached.tmdb_id = str(tmdb_id) if tmdb_id else None

        # Check for missing NFO files
        logger.info(f"Checking for missing series NFO files across {len(all_series)} series...")
        nfo_created_count = 0
        for series in all_series:
            series_id = int(series['series_id'])
            name = series['name']
            cat_id = series['category_id']
            
            cat_name = cat_map.get(cat_id, "Uncategorized")
            safe_cat = fm.sanitize_name(cat_name)
            safe_name = fm.sanitize_name(name)
            tmdb_id = series.get('tmdb')
            tmdb_suffix = fm.format_tmdb_suffix(tmdb_id)

            series_dir = f"{fm.output_dir}/{safe_cat}/{safe_name}{tmdb_suffix}"
            tvshow_nfo_path = f"{series_dir}/tvshow.nfo"

            if os.path.exists(series_dir) and not os.path.exists(tvshow_nfo_path):
                await fm.write_nfo(tvshow_nfo_path, fm.generate_show_nfo(series, prefix_regex, format_date, clean_name))
                nfo_created_count += 1
        
        if nfo_created_count > 0:
            logger.info(f"Created {nfo_created_count} missing series NFO files")

        sync_state.items_added = len(to_add_update)
        sync_state.items_deleted = len(to_delete)
        sync_state.status = SyncStatus.SUCCESS
        sync_state.progress_current = 0
        sync_state.progress_total = 0
        sync_state.progress_phase = None
        db.commit()

    except Exception as e:
        logger.exception("Error syncing series")
        sync_state.status = SyncStatus.FAILED
        sync_state.error_message = str(e)
        sync_state.progress_current = 0
        sync_state.progress_total = 0
        sync_state.progress_phase = None
        db.commit()
        raise

@celery_app.task
def sync_movies_task(subscription_id: int):
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            logger.error(f"Subscription {subscription_id} not found")
            return "Subscription not found"
        
        if not sub.is_active:
            logger.info(f"Subscription {sub.name} is inactive")
            return "Subscription inactive"

        xc = XtreamClient(sub.xtream_url, sub.username, sub.password)
        fm = FileManager(sub.movies_dir)
        
        asyncio.run(process_movies(db, xc, fm, subscription_id))
        return f"Movies synced successfully for {sub.name}"
    finally:
        db.close()

@celery_app.task
def sync_series_task(subscription_id: int):
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            logger.error(f"Subscription {subscription_id} not found")
            return "Subscription not found"
        
        if not sub.is_active:
            logger.info(f"Subscription {sub.name} is inactive")
            return "Subscription inactive"

        xc = XtreamClient(sub.xtream_url, sub.username, sub.password)
        fm = FileManager(sub.series_dir)
        
        asyncio.run(process_series(db, xc, fm, subscription_id))
        return f"Series synced successfully for {sub.name}"
    finally:
        db.close()

@celery_app.task
def check_schedules_task():
    """Check schedules and trigger syncs if needed"""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Get enabled schedules that are due
        schedules = db.query(Schedule).filter(
            Schedule.enabled == True,
            Schedule.next_run <= now
        ).all()
        
        for schedule in schedules:
            # Create execution record
            execution = ScheduleExecution(
                schedule_id=schedule.id,
                status=ExecutionStatus.RUNNING
            )
            db.add(execution)
            db.commit()
            
            try:
                # Trigger appropriate sync
                if schedule.type == ScheduleSyncType.MOVIES:
                    result = sync_movies_task.apply_async(args=[schedule.subscription_id])
                else:
                    result = sync_series_task.apply_async(args=[schedule.subscription_id])
                
                # Update execution status
                execution.status = ExecutionStatus.SUCCESS
                execution.completed_at = datetime.utcnow()
                
                # Get items processed from sync state
                sync_state = db.query(SyncState).filter(
                    SyncState.subscription_id == schedule.subscription_id,
                    SyncState.type == (SyncType.MOVIES if schedule.type == ScheduleSyncType.MOVIES else SyncType.SERIES)
                ).first()
                if sync_state:
                    execution.items_processed = (sync_state.items_added or 0) + (sync_state.items_deleted or 0)
                
            except Exception as e:
                logger.exception(f"Error executing scheduled sync for {schedule.type}")
                execution.status = ExecutionStatus.FAILED
                execution.error_message = str(e)
                execution.completed_at = datetime.utcnow()
            
            # Update schedule for next run
            schedule.last_run = now
            schedule.next_run = schedule.calculate_next_run()
            db.commit()
            
    finally:
        db.close()
