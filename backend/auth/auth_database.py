"""SQLAlchemy adapter for the small parameterized auth SQL interface."""
from sqlalchemy import create_engine,text,event
from contextlib import contextmanager

class Result:
    def __init__(self,result):self.result=result;self.rowcount=result.rowcount
    def fetchone(self):return self.result.mappings().fetchone()
    def fetchall(self):return self.result.mappings().fetchall()

class Connection:
    def __init__(self,connection):self.connection=connection
    def execute(self,sql,parameters=()):
        parts=sql.split('?')
        if len(parts)-1!=len(parameters):raise ValueError('Auth SQL parameter mismatch')
        statement=parts[0]+''.join(':p'+str(i)+part for i,part in enumerate(parts[1:]))
        return Result(self.connection.execute(text(statement),{'p'+str(i):value for i,value in enumerate(parameters)}))
    def executescript(self,script):
        for statement in script.split(';'):
            if statement.strip():self.connection.execute(text(statement))

class AuthDatabase:
    def __init__(self,url):
        self.engine=create_engine(url,pool_pre_ping=True)
        if self.engine.dialect.name == 'sqlite':
            @event.listens_for(self.engine, 'connect')
            def enforce_foreign_keys(connection, connection_record):
                # Match AuthManager's legacy SQLite FK enforcement.
                cursor=connection.cursor()
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.close()
    @contextmanager
    def connect(self):
        with self.engine.begin() as connection:yield Connection(connection)
