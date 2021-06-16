from datetime import datetime
from fastapi import Depends, HTTPException, status, APIRouter
from pydantic import BaseModel

from dependencies import get_current_user
from database import db
from database import db_schema


router = APIRouter()


class UserBody(BaseModel):
    name: str
    username: str


class DeckBody(BaseModel):
    title: str


class DeckCardBody(BaseModel):
    title: str
    content: str


class MoveCardBody(BaseModel):
    card_id: str
    is_correct: bool


class DeckUtility:

    @staticmethod
    def is_deck_exists(user_id, deck_id):
        decks = db.sql(
            '''
            SELECT id
            FROM {db_schema}.deck
            WHERE id='{deck_id}' AND user_id='{user_id}'
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                deck_id=deck_id,
                user_id=user_id
            )
        )
        if not decks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Deck not found',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        return None

    @staticmethod
    def is_card_title_exists_in_deck(deck_id, title):
        cards = db.sql(
            '''
            SELECT id
            FROM {db_schema}.deck_card
            WHERE deck_id='{deck_id}' AND title='{title}'
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                deck_id=deck_id,
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
    def get_next_order_number(deck_id):
        order_numbers = db.sql(
            '''
            SELECT order_number
            FROM {db_schema}.deck_card
            WHERE deck_id='{deck_id}'
            ORDER BY order_number DESC
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                deck_id=deck_id
            )
        )
        if order_numbers:
            return order_numbers[0]['order_number'] + 1
        return 1

    @staticmethod
    def create_revision_logs(deck_id, session_id):
        total_cards = 0
        boxes_info = db.sql(
            '''
            SELECT deck_card_id, current_box
            FROM {db_schema}.revision_log
            WHERE deck_id='{deck_id}' AND is_active=true
            '''.format(
                db_schema=db_schema,
                deck_id=deck_id
            )
        )
        if boxes_info:
            pass
        else:
            # Move all cards to BOX-1
            card_ids = db.sql(
                '''
                SELECT id
                FROM {db_schema}.deck_card
                WHERE deck_id='{deck_id}'
                ORDER BY order_number
                '''.format(
                    db_schema=db_schema,
                    deck_id=deck_id
                )
            )
            cards_to_box_1 = list()
            for card_id_item in card_ids:
                card_id = card_id_item['id']
                cards_to_box_1.append({
                    'deck_id': deck_id,
                    'deck_card_id': card_id,
                    'current_box': 'BOX_1',
                    'is_active': True,
                    'session_id': session_id
                })
            db.insert(db_schema, 'revision_log', cards_to_box_1)
            total_cards = len(card_ids)

        return total_cards

    @staticmethod
    def get_card(card_id, deck_id):
        card = db.sql(
            '''
            SELECT *
            FROM {db_schema}.deck_card
            WHERE id='{card_id}' AND deck_id='{deck_id}'
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                card_id=card_id,
                deck_id=deck_id
            )
        )
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Card not found',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        return card[0]

    @staticmethod
    def get_session(session):
        session = db.sql(
            '''
            SELECT *
            FROM {db_schema}.revision_session
            WHERE id='{session}'
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                session=session,
            )
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Session not found',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        return session[0]

    @staticmethod
    def move_card(session_id, card_id, is_correct):
        NEXT_BOX_MAP = {'BOX_1': 'BOX_2', 'BOX_2': 'BOX3'}
        curr_revision_log = db.sql(
            '''
            SELECT id, current_box, deck_id
            FROM {db_schema}.revision_log
                WHERE
                    session_id='{session_id}'
                    AND deck_card_id='{card_id}'
                    AND is_active=true
            LIMIT 1
            '''.format(
                db_schema=db_schema,
                session_id=session_id,
                card_id=card_id
            )
        )
        if not curr_revision_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Revision log not found for this card',
                headers={'WWW-Authenticate': 'Bearer'},
            )

        curr_revision_log = curr_revision_log[0]
        curr_revision_log_id = curr_revision_log['id']
        deck_id = curr_revision_log['deck_id']
        current_box = curr_revision_log['current_box']

        if is_correct:
            next_box = NEXT_BOX_MAP[current_box]
        else:
            next_box = 'BOX_1'

        # --- Mark session as started ---
        db.update(
            db_schema,
            'revision_session',
            [{
                'id': session_id,
                'is_started': True
            }])

        # --- Update current log to inactive ---
        db.update(
            db_schema,
            'revision_log',
            [{
                'id': curr_revision_log_id,
                'is_active': False,
                'moved_to': next_box
            }])

        # --- Create new log ---
        db.insert(
            db_schema,
            'revision_log',
            [{
                'deck_id': deck_id,
                'deck_card_id': card_id,
                'current_box': next_box,
                'is_active': True,
                'session_id': session_id
            }])

    @staticmethod
    def get_cards_in_session(session_id):
        week = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        today = datetime.today().weekday()
        today = week[today]

        if today in ['SAT', 'SUN']:
            # TODO: handle this ...
            return []  # nothing to revise today

        boxes = ['BOX_1']

        if today in ['TUE', 'THU']:
            boxes.insert(0, 'BOX_2')

        elif today == 'FRI':
            boxes.insert(0, 'BOX_3')

        boxes_str = ''
        for i, x in enumerate(boxes):
            boxes_str += f"'{x}'"
            if i != len(boxes) - 1:
                boxes_str += ', '

        cards_in_session = db.sql(
            '''
            SELECT log.id, log.current_box, c.id as card_id, c.title, c.content
            FROM
                {db_schema}.revision_log log
                INNER JOIN {db_schema}.deck_card c ON log.deck_card_id = c.id
            WHERE
                log.session_id='{session_id}'
                AND log.is_active=true
                AND log.current_box in ({boxes_str})
            ORDER BY log.__updatedtime__
            '''.format(
                db_schema=db_schema,
                session_id=session_id,
                boxes_str=boxes_str
            )
        )
        card = None
        remaining_cards = 0
        if cards_in_session:
            card = cards_in_session[0]
            remaining_cards = len(cards_in_session) - 1

        return card, remaining_cards

    @staticmethod
    def mark_session_all_complete(session_id):
        db.sql(
            '''
            UPDATE {db_schema}.revision_session
            SET is_completed=true
            WHERE id='{session_id}'
            '''.format(
                db_schema=db_schema,
                session_id=session_id,
            )
        )


@router.get('/decks/')
async def get_decks(current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    decks = db.search_by_value(
        db_schema,
        'deck',
        'user_id',
        user_id,
        get_attributes=['id', 'title'])
    return decks


@router.post('/decks/')
async def create_deck(
        data: DeckBody,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    deck = db.insert(
        db_schema,
        'deck',
        [{
            'user_id': user_id,
            'title': data.title
        }])
    return deck


@router.put('/decks/{deck_id}/')
async def update_deck(
        deck_id: str,
        data: DeckBody,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    DeckUtility.is_deck_exists(user_id=user_id, deck_id=deck_id)
    deck = db.update(
        db_schema,
        'deck',
        [{
            'id': deck_id,
            'user_id': user_id,
            'title': data.title
        }])
    return deck


@router.post('/decks/{deck_id}/cards/')
async def add_card_to_deck(
        deck_id: str,
        data: DeckCardBody,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    DeckUtility.is_deck_exists(user_id=user_id, deck_id=deck_id)
    DeckUtility.is_card_title_exists_in_deck(deck_id=deck_id, title=data.title)
    order_number = DeckUtility.get_next_order_number(deck_id=deck_id)

    deck_card = db.insert(
        db_schema,
        'deck_card',
        [{
            'deck_id': deck_id,
            'user_id': user_id,
            'order_number': order_number,
            'title': data.title,
            'content': data.content
        }])
    inserted_card_id = deck_card['inserted_hashes'][0]

    # --- Add card to the active session ---
    active_session = db.sql(
        '''
        SELECT id
        FROM {db_schema}.revision_session
            WHERE
                deck_id='{deck_id}'
                AND is_active=true
        LIMIT 1
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id
        )
    )
    if active_session:
        session_id = active_session[0]['id']
        db.insert(
            db_schema,
            'revision_log',
            [{
                'deck_id': deck_id,
                'deck_card_id': inserted_card_id,
                'current_box': 'BOX_1',
                'is_active': True,
                'session_id': session_id
            }])

    return deck_card


@router.get('/decks/{deck_id}/cards/')
async def get_cards(
        deck_id: str,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    deck_cards = db.sql(
        '''
        SELECT id, title, content
        FROM {db_schema}.deck_card
        WHERE deck_id='{deck_id}' AND user_id='{user_id}'
        ORDER BY order_number
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id,
            user_id=user_id)
    )
    return deck_cards


@router.post('/decks/{deck_id}/start-revision/')
async def start_revision_for_a_deck(
        deck_id: str,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    DeckUtility.is_deck_exists(user_id=user_id, deck_id=deck_id)
    session_date = str(datetime.now().date())
    session = db.insert(
        db_schema,
        'revision_session',
        [{
            'deck_id': deck_id,
            'session_date': session_date,
            'next_session_date': None,
            'total_cards': 0,
            'correct_cards_count': 0,
            'incorrect_cards_count': 0,
            'is_active': True,
            'is_completed': False,
            'is_missed': False
        }])
    session_id = session['inserted_hashes'][0]
    total_cards = \
        DeckUtility.create_revision_logs(deck_id=deck_id, session_id=session_id)
    db.update(
        db_schema,
        'revision_session',
        [{
            'id': session_id,
            'deck_id': deck_id,
            'total_cards': total_cards,
        }])
    return session


@router.get('/sessions/{session}/next-card/')
async def next_card_in_session(
        session: str = Depends(DeckUtility.get_session),
        current_user: UserBody = Depends(get_current_user)):
    session_id = session['id']
    card, remaining_cards = \
        DeckUtility.get_cards_in_session(session_id=session_id)

    is_session_completed = False
    if not card:
        is_session_completed = True
        DeckUtility.mark_session_all_complete(session_id=session_id)

    return {
        'is_session_completed': is_session_completed,
        'remaining_cards': remaining_cards,
        'card': card
    }


@router.post('/sessions/{session}/move-card/')
async def move_card_in_session(
        data: MoveCardBody,
        session: str = Depends(DeckUtility.get_session),
        current_user: UserBody = Depends(get_current_user)):
    session_id = session['id']
    card_id = data.card_id
    is_correct = data.is_correct
    deck_id = session['deck_id']
    DeckUtility.get_card(card_id=card_id, deck_id=deck_id)
    DeckUtility.move_card(session_id, card_id, is_correct)
    return 'Card moved'


@router.post('/del')
def del_rev():
    db.sql('delete from flash.revision_session')
    db.sql('delete from flash.revision_log')
    return
