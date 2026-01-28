import os
import aiofiles
import re
from typing import Optional

class FileManager:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def format_tmdb_suffix(self, tmdb_id) -> str:
        """Return ' {tmdb-XXXXX}' if valid TMDB ID, else empty string"""
        if tmdb_id:
            tmdb_str = str(tmdb_id).strip()
            if tmdb_str and tmdb_str.lower() not in ['null', 'none', '0', '']:
                try:
                    if int(tmdb_str) > 0:
                        return f" {{tmdb-{tmdb_str}}}"
                except (ValueError, TypeError):
                    pass
        return ""

    def sanitize_name(self, name: str) -> str:
        # Replace invalid characters with underscore
        sanitized = re.sub(r'[\\/:*?"<>|]', '_', name)
        
        # Truncate to max 200 characters to ensure full path stays under 255
        # (leaving room for directory path, extension, etc.)
        max_length = 200
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized


    def ensure_directory(self, path: str):
        os.makedirs(path, exist_ok=True)

    async def write_strm(self, path: str, url: str):
        async with aiofiles.open(path, 'w') as f:
            await f.write(url)

    async def write_nfo(self, path: str, content: str):
        async with aiofiles.open(path, 'w') as f:
            await f.write(content)

    async def delete_file(self, path: str):
        if os.path.exists(path):
            os.remove(path)

    async def delete_directory_if_empty(self, path: str):
        try:
            os.rmdir(path)
        except OSError:
            pass # Directory not empty

    def generate_movie_nfo(self, movie_data: dict, prefix_regex: Optional[str] = None, format_date: bool = False, clean_name: bool = False) -> str:
        """Generate NFO file for a movie with all available metadata"""
        tmdb_id = movie_data.get('tmdb', '')  # Xtream API uses 'tmdb' not 'tmdb_id'
        imdb_id = movie_data.get('imdb_id') or movie_data.get('imdb', '')  # IMDB ID

        # Use o_name as title if available, otherwise name
        title = movie_data.get('o_name') or movie_data.get('name', 'Unknown')

        # Strip language prefix if present (e.g. "FR - ", "TN - ", "ARA - ")
        # Use provided regex or default
        regex = prefix_regex if prefix_regex else r'^(?:[A-Za-z0-9.-]+_|[A-Za-z]{2,}\s*-\s*)'
        try:
            title = re.sub(regex, '', title)
        except re.error:
            # Fallback to default if custom regex is invalid
            title = re.sub(r'^(?:[A-Za-z0-9.-]+_|[A-Za-z]{2,}\s*-\s*)', '', title)

        # Format date at end: "Name_2024" -> "Name (2024)"
        if format_date:
            title = re.sub(r'[_\s](\d{4})$', r' (\1)', title)

        # Clean name: replace underscores with spaces
        if clean_name:
            title = title.replace('_', ' ')

        # Check if TMDB ID is valid (not empty, not null, not 0, not "0")
        has_valid_tmdb = False
        if tmdb_id:
            tmdb_str = str(tmdb_id).strip()
            if tmdb_str and tmdb_str.lower() not in ['null', 'none', '0', '']:
                try:
                    if int(tmdb_str) > 0:
                        has_valid_tmdb = True
                except (ValueError, TypeError):
                    pass

        # Check if IMDB ID is valid (should start with 'tt')
        has_valid_imdb = False
        if imdb_id:
            imdb_str = str(imdb_id).strip()
            if imdb_str and imdb_str.lower() not in ['null', 'none', '0', '']:
                has_valid_imdb = True

        # Get all available Xtream metadata
        plot = movie_data.get('plot') or movie_data.get('description', '')
        year = movie_data.get('year') or movie_data.get('releasedate', '')
        rating = movie_data.get('rating') or movie_data.get('rating_5based', '')
        genre = movie_data.get('genre', '')
        director = movie_data.get('director', '')
        cast_list = movie_data.get('cast') or movie_data.get('actors', '')
        duration = movie_data.get('duration') or movie_data.get('episode_run_time', '')
        trailer = movie_data.get('youtube_trailer', '')
        cover = movie_data.get('movie_image') or movie_data.get('cover_big') or movie_data.get('stream_icon') or movie_data.get('backdrop_path_original', '')
        # Content rating (MPAA) - try various field names
        mpaa = movie_data.get('mpaa') or movie_data.get('content_rating') or movie_data.get('certification') or movie_data.get('age_rating', '')

        # Handle backdrop/fanart
        backdrop_path = movie_data.get('backdrop_path', [])
        fanart = backdrop_path[0] if isinstance(backdrop_path, list) and backdrop_path else ''

        # Convert rating from 5-based to 10-based if needed
        if rating and str(rating_5based := movie_data.get('rating_5based')):
            try:
                rating = float(rating_5based) * 2
            except (ValueError, TypeError):
                pass

        nfo = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<movie>\n'

        # Essential fields
        nfo += f'  <title>{self._escape_xml(title)}</title>\n'

        if plot:
            nfo += f'  <plot>{self._escape_xml(plot)}</plot>\n'
            nfo += f'  <outline>{self._escape_xml(plot[:200])}</outline>\n'

        # User rating (on 10 scale)
        if rating:
            try:
                rating_val = float(rating)
                nfo += f'  <userrating>{int(round(rating_val))}</userrating>\n'
            except (ValueError, TypeError):
                pass

        # MPAA content rating
        if mpaa:
            nfo += f'  <mpaa>{self._escape_xml(mpaa)}</mpaa>\n'

        # Unique IDs - TMDB first (default), then IMDB
        if has_valid_tmdb:
            nfo += f'  <uniqueid type="tmdb" default="true">{tmdb_id}</uniqueid>\n'
        if has_valid_imdb:
            nfo += f'  <uniqueid type="imdb">{imdb_id}</uniqueid>\n'

        if year:
            # Extract year if it's a full date
            year_str = str(year)[:4] if len(str(year)) >= 4 else str(year)
            nfo += f'  <year>{year_str}</year>\n'

        # Genre - handle both comma and slash separators
        if genre:
            for g in re.split(r'[,/]', str(genre)):
                g = g.strip()
                if g:
                    nfo += f'  <genre>{self._escape_xml(g)}</genre>\n'

        # Director
        if director:
            nfo += f'  <director>{self._escape_xml(director)}</director>\n'

        # Cast
        if cast_list:
            for actor in str(cast_list).split(','):
                actor_name = actor.strip()
                if actor_name:
                    nfo += f'  <actor><name>{self._escape_xml(actor_name)}</name></actor>\n'

        # Duration (in minutes)
        if duration:
            try:
                # Duration might be in format "HH:MM:SS" or just minutes
                if ':' in str(duration):
                    parts = str(duration).split(':')
                    total_mins = int(parts[0]) * 60 + int(parts[1])
                else:
                    total_mins = int(duration)
                nfo += f'  <runtime>{total_mins}</runtime>\n'
            except (ValueError, TypeError, IndexError):
                pass

        # Trailer
        if trailer:
            nfo += f'  <trailer>plugin://plugin.video.youtube/?action=play_video&amp;videoid={trailer}</trailer>\n'

        # Artwork
        if cover:
            nfo += f'  <thumb>{cover}</thumb>\n'

        if fanart:
            nfo += f'  <fanart><thumb>{fanart}</thumb></fanart>\n'
        elif cover:
            nfo += f'  <fanart><thumb>{cover}</thumb></fanart>\n'

        nfo += '</movie>'
        return nfo


    def generate_show_nfo(self, series_data: dict, prefix_regex: Optional[str] = None, format_date: bool = False, clean_name: bool = False) -> str:
        """Generate NFO file for a TV show with all available metadata"""
        tmdb_id = series_data.get('tmdb', '')  # Xtream API uses 'tmdb' not 'tmdb_id'
        imdb_id = series_data.get('imdb_id') or series_data.get('imdb', '')  # IMDB ID

        # Use o_name as title if available, otherwise name
        title = series_data.get('o_name') or series_data.get('name', 'Unknown')

        # Strip language prefix if present (e.g. "FR - ", "TN - ", "ARA - ")
        # Use provided regex or default
        regex = prefix_regex if prefix_regex else r'^(?:[A-Za-z0-9.-]+_|[A-Za-z]{2,}\s*-\s*)'
        try:
            title = re.sub(regex, '', title)
        except re.error:
            # Fallback to default if custom regex is invalid
            title = re.sub(r'^(?:[A-Za-z0-9.-]+_|[A-Za-z]{2,}\s*-\s*)', '', title)

        # Format date at end: "Name_2024" -> "Name (2024)"
        if format_date:
            title = re.sub(r'[_\s](\d{4})$', r' (\1)', title)

        # Clean name: replace underscores with spaces
        if clean_name:
            title = title.replace('_', ' ')

        # Check if TMDB ID is valid (not empty, not null, not 0, not "0")
        has_valid_tmdb = False
        if tmdb_id:
            tmdb_str = str(tmdb_id).strip()
            if tmdb_str and tmdb_str.lower() not in ['null', 'none', '0', '']:
                try:
                    if int(tmdb_str) > 0:
                        has_valid_tmdb = True
                except (ValueError, TypeError):
                    pass

        # Check if IMDB ID is valid (should start with 'tt')
        has_valid_imdb = False
        if imdb_id:
            imdb_str = str(imdb_id).strip()
            if imdb_str and imdb_str.lower() not in ['null', 'none', '0', '']:
                has_valid_imdb = True

        # Get all available Xtream metadata
        plot = series_data.get('plot') or series_data.get('description', '')
        year = series_data.get('year') or series_data.get('releaseDate', '')
        rating = series_data.get('rating') or series_data.get('rating_5based', '')
        genre = series_data.get('genre', '')
        cast_list = series_data.get('cast') or series_data.get('actors', '')
        director = series_data.get('director', '')
        cover = series_data.get('cover') or series_data.get('cover_big') or series_data.get('stream_icon') or series_data.get('backdrop_path_original', '')
        # Content rating (MPAA) - try various field names
        mpaa = series_data.get('mpaa') or series_data.get('content_rating') or series_data.get('certification') or series_data.get('age_rating', '')

        # Handle backdrop/fanart
        backdrop_path = series_data.get('backdrop_path', [])
        fanart = backdrop_path[0] if isinstance(backdrop_path, list) and backdrop_path else ''

        # Convert rating from 5-based to 10-based if needed
        if rating and str(rating_5based := series_data.get('rating_5based')):
            try:
                rating = float(rating_5based) * 2
            except (ValueError, TypeError):
                pass

        nfo = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<tvshow>\n'

        nfo += f'  <title>{self._escape_xml(title)}</title>\n'

        if plot:
            nfo += f'  <plot>{self._escape_xml(plot)}</plot>\n'

        # User rating (on 10 scale)
        if rating:
            try:
                rating_val = float(rating)
                # Round to integer for userrating
                nfo += f'  <userrating>{int(round(rating_val))}</userrating>\n'
            except (ValueError, TypeError):
                pass

        # MPAA content rating
        if mpaa:
            nfo += f'  <mpaa>{self._escape_xml(mpaa)}</mpaa>\n'

        # Unique IDs - TMDB first (default), then IMDB
        if has_valid_tmdb:
            nfo += f'  <uniqueid type="tmdb" default="true">{tmdb_id}</uniqueid>\n'
        if has_valid_imdb:
            nfo += f'  <uniqueid type="imdb">{imdb_id}</uniqueid>\n'

        if year:
            year_str = str(year)[:4] if len(str(year)) >= 4 else str(year)
            nfo += f'  <year>{year_str}</year>\n'
            nfo += f'  <premiered>{year_str}</premiered>\n'

        # Genre - handle both comma and slash separators
        if genre:
            for g in re.split(r'[,/]', str(genre)):
                g = g.strip()
                if g:
                    nfo += f'  <genre>{self._escape_xml(g)}</genre>\n'

        if director:
            nfo += f'  <director>{self._escape_xml(director)}</director>\n'

        if cast_list:
            for actor in str(cast_list).split(','):
                actor_name = actor.strip()
                if actor_name:
                    nfo += f'  <actor><name>{self._escape_xml(actor_name)}</name></actor>\n'

        if cover:
            nfo += f'  <thumb>{cover}</thumb>\n'

        if fanart:
            nfo += f'  <fanart><thumb>{fanart}</thumb></fanart>\n'
        elif cover:
            nfo += f'  <fanart><thumb>{cover}</thumb></fanart>\n'

        nfo += '</tvshow>'
        return nfo

    def generate_episode_nfo(self, ep_data, series_name: str, season: int, episode: int,
                             prefix_regex: Optional[str] = None, format_date: bool = False, clean_name: bool = False) -> str:
        """Generate NFO file for a TV episode with runtime and technical details"""
        # Handle case where ep_data might be a list or other non-dict type
        if isinstance(ep_data, list):
            # If it's a list, try to get the first item or use empty dict
            ep_data = ep_data[0] if ep_data else {}
        if not isinstance(ep_data, dict):
            ep_data = {}

        # Get episode info dict (contains duration, video, audio details)
        info = ep_data.get('info', {})
        if isinstance(info, list):
            info = info[0] if info else {}
        if not isinstance(info, dict):
            info = {}

        title = ep_data.get('title', f'Episode {episode}')

        # Clean up title - remove redundant series name prefix if present
        if title.lower().startswith(series_name.lower()):
            title = title[len(series_name):].strip(' -:')
        if not title:
            title = f'Episode {episode}'

        # Apply prefix stripping if configured
        regex = prefix_regex if prefix_regex else r'^(?:[A-Za-z0-9.-]+_|[A-Za-z]{2,}\s*-\s*)'
        try:
            title = re.sub(regex, '', title)
        except re.error:
            title = re.sub(r'^(?:[A-Za-z0-9.-]+_|[A-Za-z]{2,}\s*-\s*)', '', title)

        # Format date and clean name
        if format_date:
            title = re.sub(r'[_\s](\d{4})$', r' (\1)', title)
        if clean_name:
            title = title.replace('_', ' ')

        # Parse runtime from duration_secs or duration
        runtime = 0
        duration_secs = info.get('duration_secs')
        if duration_secs:
            try:
                runtime = int(float(duration_secs)) // 60
            except (ValueError, TypeError):
                pass
        if not runtime:
            duration = info.get('duration', '')
            if duration:
                try:
                    if ':' in str(duration):
                        parts = str(duration).split(':')
                        if len(parts) >= 2:
                            runtime = int(parts[0]) * 60 + int(parts[1])
                    else:
                        runtime = int(duration)
                except (ValueError, TypeError, IndexError):
                    pass

        # Build NFO
        nfo = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<episodedetails>\n'
        nfo += f'  <title>{self._escape_xml(title)}</title>\n'
        nfo += f'  <showtitle>{self._escape_xml(series_name)}</showtitle>\n'
        nfo += f'  <season>{season}</season>\n'
        nfo += f'  <episode>{episode}</episode>\n'

        if runtime > 0:
            nfo += f'  <runtime>{runtime}</runtime>\n'

        # Add fileinfo/streamdetails if video or audio info available
        video = info.get('video', {})
        audio = info.get('audio', {})
        bitrate = info.get('bitrate')

        if video or audio:
            nfo += '  <fileinfo>\n    <streamdetails>\n'

            if video:
                nfo += '      <video>\n'
                if video.get('codec_name'):
                    nfo += f'        <codec>{self._escape_xml(video["codec_name"])}</codec>\n'
                if video.get('width') and video.get('height'):
                    nfo += f'        <width>{video["width"]}</width>\n'
                    nfo += f'        <height>{video["height"]}</height>\n'
                if video.get('display_aspect_ratio'):
                    nfo += f'        <aspect>{self._escape_xml(video["display_aspect_ratio"])}</aspect>\n'
                if duration_secs:
                    try:
                        nfo += f'        <durationinseconds>{int(float(duration_secs))}</durationinseconds>\n'
                    except (ValueError, TypeError):
                        pass
                if bitrate:
                    try:
                        nfo += f'        <bitrate>{int(bitrate)}</bitrate>\n'
                    except (ValueError, TypeError):
                        pass
                nfo += '      </video>\n'

            if audio:
                nfo += '      <audio>\n'
                if audio.get('codec_name'):
                    nfo += f'        <codec>{self._escape_xml(audio["codec_name"])}</codec>\n'
                if audio.get('channels'):
                    nfo += f'        <channels>{audio["channels"]}</channels>\n'
                if audio.get('sample_rate'):
                    nfo += f'        <samplerate>{audio["sample_rate"]}</samplerate>\n'
                if audio.get('channel_layout'):
                    nfo += f'        <layout>{self._escape_xml(audio["channel_layout"])}</layout>\n'
                # Try to get language from tags
                audio_tags = audio.get('tags', {})
                if audio_tags.get('language'):
                    nfo += f'        <language>{self._escape_xml(audio_tags["language"])}</language>\n'
                nfo += '      </audio>\n'

            nfo += '    </streamdetails>\n  </fileinfo>\n'

        nfo += '</episodedetails>'
        return nfo

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters"""
        if not text:
            return ''
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
