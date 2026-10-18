"""Script to create test database."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
import asyncpg


async def create_test_db():
    """Create the test database."""
    try:
        # Connect to postgres database to create test database
        conn = await asyncpg.connect(
            user='postgres',
            password=os.environ['POSTGRES_PASSWORD'],
            host='localhost',
            port=5432,
            database='postgres'
        )
        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'docfoundry_test'"
        )
        if not exists:
            await conn.execute('CREATE DATABASE docfoundry_test')
            print('Test database created successfully')
        else:
            print('Test database already exists')
        await conn.close()
    except Exception as e:
        print(f'Error creating test database: {e}')


if __name__ == '__main__':
    asyncio.run(create_test_db())

