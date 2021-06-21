import harperdb
from app.config import settings

print('-' * 25)
db = harperdb.HarperDB(
    url=settings.db_url,
    username=settings.db_username,
    password=settings.db_password
)
db_schema = settings.db_schema_name
print('Harper DB connected')
print('-' * 25)
