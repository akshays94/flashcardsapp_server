from datetime import datetime
from fastapi import Depends, HTTPException, status, APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.dependencies import get_current_user_id
from app.database import db
from app.database import db_schema


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
    def get_todays_boxes(deck_id, session_id):
        week = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        today = datetime.today().weekday()
        today = week[today]

        is_not_first_session = db.sql(
            '''
            SELECT TOP 1 id
            FROM {db_schema}.revision_session
            WHERE deck_id='{deck_id}'
            AND id!='{session_id}'
            AND is_completed=true
            '''.format(
                db_schema=db_schema,
                deck_id=deck_id,
                session_id=session_id
            )
        )

        if is_not_first_session:
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

            return boxes, boxes_str
        else:
            return ['BOX_1'], "'BOX_1'"

    @staticmethod
    def create_revision_logs(deck_id, session_id):
        total_cards = 0
        boxes_info = db.sql(
            '''
            SELECT TOP 1 id
            FROM {db_schema}.revision_log
            WHERE deck_id='{deck_id}'
            '''.format(
                db_schema=db_schema,
                deck_id=deck_id
            )
        )

        if boxes_info:
            boxes, boxes_str = DeckUtility.get_todays_boxes(deck_id, session_id)
            print('*** todays', boxes, boxes_str)
            count = db.sql(
                '''
                SELECT count(*)
                FROM {db_schema}.revision_log
                WHERE
                    deck_id='{deck_id}'
                    AND is_active=true
                    AND current_box in ({boxes_str})
                '''.format(
                    db_schema=db_schema,
                    deck_id=deck_id,
                    boxes_str=boxes_str
                )
            )
            total_cards = count[0]['COUNT(*)']

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
    def get_card_from_db(card_id):
        card = db.search_by_hash(db_schema, 'deck_card', [card_id], ['id'])
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Card not found',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        return card[0]

    @staticmethod
    def get_deck_from_db(deck_id):
        deck = db.search_by_hash(db_schema, 'deck', [deck_id], ['id'])
        if not deck:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Deck not found',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        return deck[0]

    @staticmethod
    def get_session_from_db(session):
        session = db.search_by_hash(
            db_schema, 'revision_session', [session], ['*'])
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
            SELECT log.id, log.current_box, log.deck_id, sesh.correct_cards_count, sesh.incorrect_cards_count, sesh.total_cards
            FROM {db_schema}.revision_log log
            INNER JOIN {db_schema}.revision_session sesh
            ON log.session_id = sesh.id
                WHERE
                    log.deck_card_id='{card_id}'
                    AND log.is_active=true
            LIMIT 1
            '''.format(
                db_schema=db_schema,
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
        correct_cards_count = curr_revision_log['correct_cards_count']
        incorrect_cards_count = curr_revision_log['incorrect_cards_count']
        total_cards = curr_revision_log['total_cards']

        if is_correct:
            next_box = NEXT_BOX_MAP[current_box]
            if correct_cards_count + incorrect_cards_count == total_cards:
                db.sql(
                    '''
                    UPDATE {db_schema}.revision_session
                    SET
                        incorrect_cards_count = incorrect_cards_count - 1,correct_cards_count = correct_cards_count + 1
                    WHERE id = '{session_id}'
                    '''.format(
                        db_schema=db_schema,
                        session_id=session_id
                    )
                )
            else:
                db.sql(
                    '''
                    UPDATE {db_schema}.revision_session
                    SET correct_cards_count = correct_cards_count + 1
                    WHERE id = '{session_id}'
                    '''.format(
                        db_schema=db_schema,
                        session_id=session_id
                    )
                )
        else:
            next_box = 'BOX_1'
            db.sql(
                '''
                UPDATE {db_schema}.revision_session
                SET incorrect_cards_count = incorrect_cards_count + 1
                WHERE id = '{session_id}'
                '''.format(
                    db_schema=db_schema,
                    session_id=session_id
                )
            )

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
    def get_cards_in_session(session_id, deck_id):
        boxes, boxes_str = DeckUtility.get_todays_boxes(deck_id, session_id)
        print(boxes, boxes_str, '<<<')

        cards_in_session = db.sql(
            '''
            SELECT log.id, log.current_box, c.id as card_id, c.title, c.content
            FROM
                {db_schema}.revision_log log
                INNER JOIN {db_schema}.deck_card c ON log.deck_card_id = c.id
            WHERE
                log.deck_id='{deck_id}'
                AND log.is_active=true
                AND log.current_box in ({boxes_str})
            ORDER BY log.__updatedtime__
            '''.format(
                db_schema=db_schema,
                deck_id=deck_id,
                boxes_str=boxes_str
            )
        )
        card = None
        remaining_cards = 0
        if cards_in_session:
            card = cards_in_session[0]
            remaining_cards = len(cards_in_session) - 1

        return card, remaining_cards


@router.get('/decks/')
async def list_decks(current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    decks = db.sql(
        '''
        SELECT id, title
        FROM {db_schema}.deck
        WHERE user_id='{user_id}'
        ORDER BY __updatedtime__ DESC
        '''.format(
            db_schema=db_schema,
            user_id=user_id
        )
    )
    return decks


@router.post('/decks/')
async def create_deck(
        data: DeckBody,
        user_id: UserBody = Depends(get_current_user_id)):
    deck = db.insert(
        db_schema,
        'deck',
        [{
            'user_id': user_id,
            'title': data.title
        }])
    deck_id = deck['inserted_hashes'][0]
    deck = {
        'id': deck_id,
        'title': data.title
    }
    return deck


@router.put('/decks/{deck_id}/')
async def update_deck(
        data: DeckBody,
        deck_id: str = Depends(DeckUtility.get_deck_from_db),
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    deck_id = deck_id['id']
    deck = db.update(
        db_schema,
        'deck',
        [{
            'id': deck_id,
            'user_id': user_id,
            'title': data.title
        }])
    return deck


@router.get('/decks/{deck_id}/')
async def retrieve_deck(
        deck_id: str,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']

    deck = db.sql(
        '''
        SELECT d.id, d.title, d.__createdtime__, COUNT(dc.id) as cards
        FROM {db_schema}.deck d
        LEFT JOIN {db_schema}.deck_card dc
        ON d.id = dc.deck_id
        WHERE d.id='{deck_id}' AND d.user_id='{user_id}'
        GROUP BY d.id, d.title, d.__createdtime__
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id,
            user_id=user_id
        )
    )
    deck = deck[0]
    today = str(datetime.now().date())
    today_session = db.sql(
        '''
        SELECT id
        FROM {db_schema}.revision_session
        WHERE deck_id='{deck_id}'
        AND session_date='{today}'
        AND is_completed=true
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id,
            today=today
        )
    )
    deck['is_todays_session_completed'] = False
    if len(today_session) > 0:
        deck['is_todays_session_completed'] = True
    return deck


def add_new_card_to_active_session(deck_id, inserted_card_id):
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


@router.post('/decks/{deck_id}/cards/')
async def add_card_to_deck(
        deck_id: str,
        data: DeckCardBody,
        background_tasks: BackgroundTasks,
        current_user: UserBody = Depends(get_current_user)):
    user_id = current_user['id']
    order_number = 1

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

    card = {
        'id': inserted_card_id,
        'title': data.title,
        'content': data.content
    }

    # --- Add card to the active session ---
    background_tasks.add_task(
        add_new_card_to_active_session,
        deck_id,
        inserted_card_id)

    return card


@router.get('/decks/{deck_id}/cards/')
async def list_cards(
        deck_id: str,
        user_id: UserBody = Depends(get_current_user_id)):
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
        user_id: UserBody = Depends(get_current_user_id)):
    session_date = str(datetime.now().date())

    session = db.sql(
        '''
        SELECT id
        FROM {db_schema}.revision_session
        WHERE deck_id='{deck_id}'
        AND session_date='{session_date}'
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id,
            session_date=session_date
        )
    )

    if session:
        session_id = session[0]['id']
    else:
        created_session = db.insert(
            db_schema,
            'revision_session',
            [{
                'deck_id': deck_id,
                'session_date': session_date,
                'total_cards': 0,
                'correct_cards_count': 0,
                'incorrect_cards_count': 0,
                'is_completed': False
            }])
        session_id = created_session['inserted_hashes'][0]

        total_cards = \
            DeckUtility.create_revision_logs(deck_id=deck_id, session_id=session_id)

        db.update(
            db_schema,
            'revision_session',
            [{
                'id': session_id,
                'total_cards': total_cards,
            }])

    session = db.sql(
        '''
        SELECT s.id, s.session_date, s.deck_id, d.title
        FROM {db_schema}.revision_session s
        INNER JOIN {db_schema}.deck d ON s.deck_id = d.id
        WHERE s.id='{session_id}'
        '''.format(
            db_schema=db_schema,
            session_id=session_id
        )
    )
    return session[0]


@router.get('/decks/{deck_id}/sessions/')
async def list_sessions(
        deck_id: str,
        user_id: UserBody = Depends(get_current_user_id)):
    sessions = db.sql(
        '''
        SELECT total_cards, correct_cards_count, is_completed, DATE_FORMAT(session_date, "DD/MM/Y") as session_date, incorrect_cards_count, id
        FROM {db_schema}.revision_session
        WHERE deck_id='{deck_id}'
        ORDER BY __createdtime__ DESC
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id
        )
    )

    db.sql(
        '''
        UPDATE {db_schema}.revision_session
        SET is_completed=true
        WHERE deck_id='{deck_id}'
        AND session_date<'{today}'::date
        AND is_completed=false
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id,
            today=str(datetime.now().date())
        )
    )
    return sessions


@router.get('/sessions/{session_id}/')
async def retrieve_session(
        session_id: str,
        user_id: UserBody = Depends(get_current_user_id)):
    session = db.sql(
        '''
        SELECT s.id, DATE_FORMAT(s.session_date, "DD/MM/Y") as session_date, s.deck_id, d.title
        FROM {db_schema}.revision_session s
        INNER JOIN {db_schema}.deck d ON s.deck_id = d.id
        WHERE s.id='{session_id}'
        '''.format(
            db_schema=db_schema,
            session_id=session_id
        )
    )
    return session[0]


@router.get('/sessions/{session}/next-card/')
async def next_card_in_session(
        session: str = Depends(DeckUtility.get_session_from_db),
        current_user: UserBody = Depends(get_current_user)):
    session_id = session['id']
    deck_id = session['deck_id']

    card, remaining_cards = \
        DeckUtility.get_cards_in_session(session_id=session_id, deck_id=deck_id)

    is_session_completed = False
    if not card:
        is_session_completed = True
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

    return {
        'is_session_completed': is_session_completed,
        'remaining_cards': remaining_cards,
        'card': card
    }


@router.post('/sessions/{session}/move-card/')
async def move_card_in_session(
        data: MoveCardBody,
        session: str = Depends(DeckUtility.get_session_from_db),
        user_id: UserBody = Depends(get_current_user_id)):
    session_id = session['id']
    card_id = data.card_id
    is_correct = data.is_correct
    DeckUtility.get_card_from_db(card_id=card_id)
    DeckUtility.move_card(session_id, card_id, is_correct)
    return 'Card moved'


@router.post('/sessions/{session}/mark-complete/')
async def mark_session_as_complete(
        session: str = Depends(DeckUtility.get_session_from_db),
        user_id: UserBody = Depends(get_current_user_id)):
    session_id = session['id']
    db.update(
        db_schema,
        'revision_session',
        [{
            'id': session_id,
            'is_completed': True
        }]
    )
    return 'Session marked as complete'


@router.delete('/decks/{deck_id}/')
def delete_deck(
        deck_id: str = Depends(DeckUtility.get_deck_from_db),
        user_id: UserBody = Depends(get_current_user_id)):
    deck_id = deck_id['id']
    db.sql(
        '''
        DELETE FROM {db_schema}.deck
        WHERE id='{deck_id}'
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id
        )
    )
    db.sql(
        '''
        DELETE FROM {db_schema}.deck_card
        WHERE deck_id='{deck_id}'
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id
        )
    )
    db.sql(
        '''
        DELETE FROM {db_schema}.revision_session
        WHERE deck_id='{deck_id}'
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id
        )
    )
    db.sql(
        '''
        DELETE FROM {db_schema}.revision_log
        WHERE deck_id='{deck_id}'
        '''.format(
            db_schema=db_schema,
            deck_id=deck_id
        )
    )
    return 'Deck deleted'


@router.delete('/cards/{card_id}/')
async def delete_card(
        card_id: str = Depends(DeckUtility.get_card_from_db),
        user_id: UserBody = Depends(get_current_user_id)):
    card_id = card_id['id']
    db.sql(
        '''
        DELETE FROM {db_schema}.deck_card
        WHERE id='{card_id}'
        '''.format(
            db_schema=db_schema,
            card_id=card_id
        )
    )
    db.sql(
        '''
        DELETE FROM {db_schema}.revision_log
        WHERE deck_card_id='{card_id}'
        '''.format(
            db_schema=db_schema,
            card_id=card_id
        )
    )
    return 'Card deleted'


# TODO: remove this API
@router.post('/del')
def del_rev():
    # db.sql('delete from flash.deck')
    # db.sql('delete from flash.deck_card')
    db.sql('delete from flash.revision_session')
    db.sql('delete from flash.revision_log')
    return 'Deleted ...'
