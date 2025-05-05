#connect to the SQL database
#enable basic database functionality

import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

#set basic class for SQL
Base = declarative_base()


#user table in database
class User(Base):

    __tablename__ = "users" #name of the table
    id = Column(Integer, primary_key=True, index=True)  #id for each row for faster lookup
    name = Column(String, index=True)   #name string column
    age = Column(Integer)   #integer age column
    email = Column(String, unique=True, index=True) #email string column
    orders = relationship("Order", back_populates="user")   #multiple orders + bidirectional between user and order


#food table in database
class Food(Base):

    __tablename__ = "food"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    price = Column(Float)
    orders = relationship("Order", back_populates="food")


#order table in database
class Order(Base):

    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    food_id = Column(Integer, ForeignKey("food.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="orders")
    food = relationship("Food", back_populates="orders")



#relative path to SQL and the database name
DATABASE_URL = "sqlite:///example.db"

#handle connection
engine = create_engine(DATABASE_URL)
#create new database objects
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



#initiaize and create databse (with initial database info hardcoded)
def init_db():

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    #hard coded user examples
    users = [
        User(name="Alice", age=30, email="alice@example.com"),
        User(name="Bob", age=25, email="bob@example.com"),
        User(name="Charlie", age=35, email="charlie@example.com"),
    ]
    session.add_all(users)
    session.commit()

    #hard coded food examples
    foods = [
        Food(name="Pizza Margherita", price=12.5),
        Food(name="Spaghetti Carbonara", price=15.0),
        Food(name="Lasagne", price=14.0),
    ]
    session.add_all(foods)
    session.commit()

    #hard coded order examples
    orders = [
        Order(food_id=1, user_id=1),
        Order(food_id=2, user_id=1),
        Order(food_id=3, user_id=2),
    ]
    
    session.add_all(orders)
    session.commit()

    session.close()


if __name__ == "__main__":
    if not os.path.exists("example.db"):
        init_db()
    else:
        print(".")