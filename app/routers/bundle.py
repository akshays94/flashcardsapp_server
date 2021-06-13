from fastapi import Depends, HTTPException, status, APIRouter
from pydantic import BaseModel

from dependencies import get_current_user
from database import db
from database import db_schema


router = APIRouter()


class UserBody(BaseModel):
    name: str
    username: str


class BundleBody(BaseModel):
    title: str


class BundleCardBody(BaseModel):
    title: str
    content: str


class BundleUtility:

    @staticmethod
    def is_bundle_exists(user_id, bundle_id):
        bundles = db.sql(
            '''
            SELECT id
            FROM {db_schema}.bundle
            WHERE id='{bundle_id}' AND user_id='{user_id}'
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                bundle_id=bundle_id,
                user_id=user_id
            )
        )
        if not bundles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Bundle not found',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        return None

    @staticmethod
    def is_card_title_exists_in_bundle(bundle_id, title):
        cards = db.sql(
            '''
            SELECT id
            FROM {db_schema}.bundle_card
            WHERE bundle_id='{bundle_id}' AND title='{title}'
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                bundle_id=bundle_id,
                title=title
            )
        )
        if cards:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Duplicate card found',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        return None

    @staticmethod
    def get_next_order_number(bundle_id):
        order_numbers = db.sql(
            '''
            SELECT order_number
            FROM {db_schema}.bundle_card
            WHERE bundle_id='{bundle_id}'
            ORDER BY order_number DESC
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                bundle_id=bundle_id
            )
        )
        if order_numbers:
            return order_numbers[0]['order_number'] + 1
        return 1


@router.get('/bundles/')
async def get_bundles(current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    bundles = db.search_by_value(
        db_schema,
        'bundle',
        'user_id',
        user_id,
        get_attributes=['title'])
    return bundles


@router.post('/bundles/')
async def create_bundle(
        data: BundleBody,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    bundle = db.insert(
        db_schema,
        'bundle',
        [{
            'user_id': user_id,
            'title': data.title
        }])
    return bundle


@router.put('/bundles/{bundle_id}/')
async def update_bundle(
        bundle_id: str,
        data: BundleBody,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    BundleUtility.is_bundle_exists(user_id=user_id, bundle_id=bundle_id)
    bundle = db.update(
        db_schema,
        'bundle',
        [{
            'id': bundle_id,
            'user_id': user_id,
            'title': data.title
        }])
    return bundle


@router.post('/bundles/{bundle_id}/cards/')
async def add_card_to_bundle(
        bundle_id: str,
        data: BundleCardBody,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    BundleUtility.is_bundle_exists(user_id=user_id, bundle_id=bundle_id)
    BundleUtility.is_card_title_exists_in_bundle(bundle_id=bundle_id, title=data.title)
    order_number = BundleUtility.get_next_order_number(bundle_id=bundle_id)

    bundle_card = db.insert(
        db_schema,
        'bundle_card',
        [{
            'bundle_id': bundle_id,
            'user_id': user_id,
            'order_number': order_number,
            'title': data.title,
            'content': data.content
        }])
    return bundle_card


@router.get('/bundles/{bundle_id}/cards/')
async def get_cards(
        bundle_id: str,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    bundle_cards = db.sql(
        '''
        SELECT id, title, content
        FROM {db_schema}.bundle_card
        WHERE bundle_id='{bundle_id}' AND user_id='{user_id}'
        ORDER BY order_number
        '''.format(
            db_schema=db_schema,
            bundle_id=bundle_id,
            user_id=user_id)
    )
    return bundle_cards
