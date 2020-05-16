from abc import ABC, abstractmethod
import pymongo

class DatabaseAPI:
    @staticmethod
    def get_database(database="Mongo", *args, **kwargs):
        databases = {"Mongo": Mongo}
        if database in databases:
            return databases[database](*args, **kwargs)
        return False

class DatabaseInterface(ABC):
    @abstractmethod
    def store_observation(self, observation):
        pass

    @abstractmethod
    def _get_game_id(self, collection):
        pass

class Mongo(DatabaseInterface):
    def __init__(self, connection_string="mongodb://localhost:27017/", database="BNO"):
        self.client = pymongo.MongoClient(connection_string)
        self.db = self.client[database]

        self.game_id = False # Stores the game ID which is an INT in ascending order

    def store_observation(self, observation, collection="Observations", duplicate=False):
        collection = self.db[collection]

        observation["game_id"] = self._get_game_id(collection)  # Find game id and add to observation

        # Checking if record is duplicate (else each action would be stored, meaning the result would have days * 10 records
        if not duplicate:
            dupe = collection.find_one(observation)

            if dupe:
                return False

        insert = collection.insert_one(observation)
        return insert.inserted_id

    def _get_game_id(self, collection):
        """
        Getting game id
        :param collection:
        :return:
        """
        if not self.game_id:
            game_id = collection.find_one({}, sort=[('game_id', pymongo.DESCENDING)], projection={'game_id': True})
            if game_id:
                self.game_id = game_id['game_id'] + 1
            else:
                self.game_id = 1

        return self.game_id