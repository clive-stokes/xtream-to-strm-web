from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.session import get_db
from app.models.selection import SelectedCategory
from app.models.category import Category
from app.models.subscription import Subscription
from app.schemas import CategoryResponse, SelectionUpdate, SyncResponse
from app.api import deps
from app.services.xtream import XtreamClient

router = APIRouter()

def get_xtream_client(db: Session, subscription_id: int) -> XtreamClient:
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if not sub.is_active:
        raise HTTPException(status_code=400, detail="Subscription is inactive")
    return XtreamClient(sub.xtream_url, sub.username, sub.password)

@router.get("/movies/{subscription_id}", response_model=List[CategoryResponse])
def get_movie_categories(subscription_id: int, db: Session = Depends(get_db)):
    """Get movie categories from database"""
    # Get all categories from database
    categories = db.query(Category).filter(
        Category.subscription_id == subscription_id,
        Category.type == "movie"
    ).all()
    
    # Get selected categories
    selected = db.query(SelectedCategory).filter(
        SelectedCategory.subscription_id == subscription_id,
        SelectedCategory.type == "movie"
    ).all()
    selected_ids = {s.category_id for s in selected}

    return [
        CategoryResponse(
            category_id=cat.category_id,
            category_name=cat.category_name,
            selected=cat.category_id in selected_ids
        )
        for cat in categories
    ]

@router.get("/series/{subscription_id}", response_model=List[CategoryResponse])
def get_series_categories(subscription_id: int, db: Session = Depends(get_db)):
    """Get series categories from database"""
    # Get all categories from database
    categories = db.query(Category).filter(
        Category.subscription_id == subscription_id,
        Category.type == "series"
    ).all()
    
    # Get selected categories
    selected = db.query(SelectedCategory).filter(
        SelectedCategory.subscription_id == subscription_id,
        SelectedCategory.type == "series"
    ).all()
    selected_ids = {s.category_id for s in selected}

    return [
        CategoryResponse(
            category_id=cat.category_id,
            category_name=cat.category_name,
            selected=cat.category_id in selected_ids
        )
        for cat in categories
    ]

@router.post("/movies/sync/{subscription_id}", response_model=SyncResponse)
async def sync_movie_categories(subscription_id: int, db: Session = Depends(get_db)):
    """Sync movie categories from Xtream to database"""
    client = get_xtream_client(db, subscription_id)
    try:
        categories = await client.get_vod_categories()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from Xtream: {str(e)}")

    # Clear existing movie categories for this subscription
    db.query(Category).filter(
        Category.subscription_id == subscription_id,
        Category.type == "movie"
    ).delete()
    
    # Add new categories
    now = datetime.utcnow()
    for cat in categories:
        db.add(Category(
            subscription_id=subscription_id,
            category_id=str(cat["category_id"]),
            category_name=cat["category_name"],
            type="movie",
            last_sync=now
        ))
    
    db.commit()
    
    return SyncResponse(
        categories_synced=len(categories),
        timestamp=now
    )

@router.post("/series/sync/{subscription_id}", response_model=SyncResponse)
async def sync_series_categories(subscription_id: int, db: Session = Depends(get_db)):
    """Sync series categories from Xtream to database"""
    client = get_xtream_client(db, subscription_id)
    try:
        categories = await client.get_series_categories()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from Xtream: {str(e)}")

    # Clear existing series categories for this subscription
    db.query(Category).filter(
        Category.subscription_id == subscription_id,
        Category.type == "series"
    ).delete()
    
    # Add new categories
    now = datetime.utcnow()
    for cat in categories:
        db.add(Category(
            subscription_id=subscription_id,
            category_id=str(cat["category_id"]),
            category_name=cat["category_name"],
            type="series",
            last_sync=now
        ))
    
    db.commit()
    
    return SyncResponse(
        categories_synced=len(categories),
        timestamp=now
    )

@router.post("/movies/{subscription_id}", response_model=List[CategoryResponse])
def update_movie_selection(subscription_id: int, selection: SelectionUpdate, db: Session = Depends(get_db)):
    """Update movie category selection"""
    # Clear existing selection for this subscription
    db.query(SelectedCategory).filter(
        SelectedCategory.subscription_id == subscription_id,
        SelectedCategory.type == "movie"
    ).delete()
    
    # Add new selection
    for cat in selection.categories:
        db.add(SelectedCategory(
            subscription_id=subscription_id,
            category_id=cat.category_id,
            name=cat.category_name,
            type="movie"
        ))
    db.commit()
    
    return [CategoryResponse(category_id=c.category_id, category_name=c.category_name, selected=True) for c in selection.categories]

@router.post("/series/{subscription_id}", response_model=List[CategoryResponse])
def update_series_selection(subscription_id: int, selection: SelectionUpdate, db: Session = Depends(get_db)):
    """Update series category selection"""
    # Clear existing selection for this subscription
    db.query(SelectedCategory).filter(
        SelectedCategory.subscription_id == subscription_id,
        SelectedCategory.type == "series"
    ).delete()
    
    # Add new selection
    for cat in selection.categories:
        db.add(SelectedCategory(
            subscription_id=subscription_id,
            category_id=cat.category_id,
            name=cat.category_name,
            type="series"
        ))
    db.commit()
    
    return [CategoryResponse(category_id=c.category_id, category_name=c.category_name, selected=True) for c in selection.categories]
