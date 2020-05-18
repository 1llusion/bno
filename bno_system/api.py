from bno_system import Player, GameSystem
from random import randint
import math
import numpy as np
from DatabaseAPI import DatabaseAPI
from collections import deque


class GameAPI:
    observation_memory = {}  # Observation memory
    @staticmethod
    def random_mode(players, player_api):
        score = []
        for player in players:
            params = [randint(0, 7), randint(0, 9), randint(0, 9), randint(0, 9)]

            observation = player_api.do_action(player, params)
            if observation:
                score.append(observation[-1])
        return score

    def compete_mode(self, model, players, player_api):
        score = []
        for uid in players:
            # Initialising observation memory
            if uid not in self.observation_memory:
                self.observation_memory[uid] = deque([[0] * 253] * 10)
            observation = player_api.observation(uid)

            self.observation_memory[uid].append(observation)
            self.observation_memory[uid].popleft()

            # I have no idea why this works. Please explain! I'm sure it's wrong..
            observation = [[self.observation_memory[uid]]]

            action = model.predict(observation)

            # Convert from numpy array to numpy int to python native int
            action = action[0][0].astype(int).item()
            # Taking the absolute value of an action
            action = abs(action)

            observation = player_api.do_action(uid, action)
            if observation:
                score.append(observation[-1])
        return score

    @staticmethod
    def nothing_mode(players, player_api):
        """
        In this mode all players do nothing
        :param players:
        :param player_api:
        :return:
        """
        score = []
        for player in players:
            observation = player_api.do_action(player, 0)
            if observation:
                score.append(observation[-1])
        return score

    class BotAPI:
        """
        Api to be used by the bots to train/make decisions.
        The main purpose is to provide abstraction for actions and provide formatted observations
        """

        player = None

        def __init__(self):
            # Used to transform action parameters to something more useful
            # Note that it only changes variables at first position - [1] in the action list
            # List length is how many variables it accepts, numbers within the list is max range
            self.actions = {
                            'do_nothing': [1],
                            'energy_to_food': [100],
                            'add_vote_for_skill_auction': [6],
                            'add_bid_for_skill_auction': [100],
                            'energy_to_coins': [100],
                            'add_vote_for_turn': [10],
                            'add_food_vote': [4],
                            'add_to_market': [100, 100],
                            'add_bid_for_food': [100, 100, 100]
                            }

            # Getting indexes of actions and mapping them to helper functions
            add_vote_for_turn = list(self.actions).index('add_vote_for_turn')
            add_bid_for_food = list(self.actions).index('add_bid_for_food')
            add_vote_for_skill_auction = list(self.actions).index('add_vote_for_skill_auction')
            add_food_vote = list(self.actions).index('add_food_vote')

            energy_to_coins = list(self.actions).index('energy_to_coins')
            energy_to_food = list(self.actions).index('energy_to_food')
            add_to_market = list(self.actions).index('add_to_market')
            add_bid_for_skill_auction = list(self.actions).index('add_bid_for_skill_auction')

            self.helpers = [{
                                add_vote_for_turn: self._param_to_uid,
                                add_bid_for_food: self._param_to_mid,
                                add_vote_for_skill_auction: self._param_to_skill,
                                add_food_vote: self._param_to_food_vote,
                                energy_to_coins: self._energy_percentage,
                                energy_to_food: self._energy_percentage,
                                add_to_market: self._coin_percentage,
                                add_bid_for_skill_auction: self._coin_percentage
                            },
                            {
                                add_bid_for_food: self._coin_percentage,
                             },
                            {
                             }
                            ]

            # Holds information on whether a bot is ready to end turn (len < 10) or ready to finish turn
            self.bot_actions = {}
            # Boundary for integer action
            self.action_boundary = self._get_boundaries()

            self.db = DatabaseAPI.get_database("Mongo")

        def observation(self, uid, save_to_db=False, ver=2):
            """
            :param uid:
            :param save_to_db:
            :param ver: Version, added for backward compatibility
            :return:
            """
            food = GameSystem.players[uid].food
            energy = GameSystem.players[uid].energy
            coins = GameSystem.players[uid].coins
            min_bid_skill = GameSystem.players[uid].skill["min_bid_skill"]
            max_bid_skill = GameSystem.players[uid].skill["max_bid_skill"]
            energy_skill = GameSystem.players[uid].skill["energy_skill"]
            money_conversion_skill = GameSystem.players[uid].skill["money_conversion_skill"]
            food_conversion_skill = GameSystem.players[uid].skill["food_conversion_skill"]
            auction_skill = GameSystem.players[uid].skill["auction_skill"]
            alive = int(GameSystem.players[uid].alive)
            self_score = GameSystem.players[uid].score

            # Food market info [amount, start_bid]
            food_market = []
            food_market_mid = list(GameSystem.food_market)
            for mid in food_market_mid[:100]: # Only a 100 markets are returned. In theory, there may be more
                if GameSystem.food_market[mid]['uid'] == uid:
                    market_amount = GameSystem.food_market[mid]['amount']
                    market_bid = GameSystem.food_market[mid]['start_bid']
                    food_market.append(market_amount if market_amount else 0)
                    food_market.append(market_bid if market_bid else 0)

            #print(len(food_market))
            # If there are less than 100 markets, append empty markets
            if len(food_market) <= 200:
                food_market.extend([0]*(200-len(food_market)))

            # System information
            food_requirement = GameSystem.food_requirement
            day = GameSystem.day
            global_min_bid = GameSystem.global_min_bid
            global_max_bid = GameSystem.global_max_bid

            scores = []
            players_alive = []
            for player in GameSystem.players:
                if player == uid:
                    continue

                scores.append(GameSystem.players[player].score)
                players_alive.append(int(GameSystem.players[player].alive))
            if save_to_db:
                db_obs = {
                            "uid": uid,
                            "alive": alive,
                            "food": food,
                            "energy": energy,
                            "coins": coins,
                            "score": self_score,
                            "other_scores": [*scores],
                            "day": day,
                            "food_requirement": food_requirement,
                            "min_bid_skill": min_bid_skill,
                            "max_bid_skill": max_bid_skill,
                            "energy_skill": energy_skill,
                            "money_conversion_skill": money_conversion_skill,
                            "food_conversion_skill": food_conversion_skill,
                            "auction_skill": auction_skill,
                            "global_min_bid": global_min_bid,
                            "global_max_bid": global_max_bid,
                            "food_market": [*food_market],
                            "players_alive": [*players_alive],
                            "action_memory": [*GameSystem.players[uid].action_memory],
                         }
                self.db.store_observation(db_obs, duplicate=False)

            if ver == 1:
                obs = [*GameSystem.players[uid].action_memory,
                       food, energy, coins,
                       min_bid_skill, max_bid_skill, energy_skill, money_conversion_skill, food_conversion_skill, auction_skill,
                       alive, food_requirement, day,
                       global_min_bid, global_max_bid, *food_market,
                       *scores, self_score]
            elif ver == 2:
                obs = [*GameSystem.players[uid].action_memory,
                       food, energy, coins,
                       min_bid_skill, max_bid_skill, energy_skill, money_conversion_skill, food_conversion_skill,
                       auction_skill,
                       alive, food_requirement, day,
                       global_min_bid, global_max_bid, *food_market,
                       *scores, *players_alive,self_score]
            return obs

        def do_action(self, uid, action):
            """
            Actions heavily depend on dictionaries being in order of assignment. Be cautious in Python < 3.7
            :param uid:
            :param action: Format is [[0, 1, 2, 3]*10] where 0 == Action ID and 1, 2, 3 are parameters
            :return:
            """
            if type(action) == int:
                action = self._int_to_actions(action)

            player = self._get_player(uid)
            self.player = player # Please please please fix this

            action_list = list(self.actions) # This might bug out in Python < 3.7
            # Checking if action is valid
            invalid_action = False
            if action[0] < len(action_list):
                action_name = action_list[action[0]]
                upper_index = len(self.actions[action_name]) + 1
                transformed_action = {"name": action_name, "params": [*action[1:upper_index]]}

                # Using helpers to translate params (player uid, market mid...)
                for i in range(3):
                    if i < upper_index - 1:
                        if action[0] in self.helpers[i]:
                            # TODO Change it so that the helper can be run on more than the 2nd element
                            action[i+1] = self.helpers[i][action[0]](action[i+1])
                            if action[i+1] < 0: # -1 means invalid parameter, therefore just skip the rest of the code
                                # As a punishment, score is set to -1
                                invalid_action = True
                                action[0] = 0

                # Action is valid, add it to bot memory
                player.action_memory.append(action[0])
                player.action_memory.popleft()

                # Appending action
                if uid in self.bot_actions:
                    if len(self.bot_actions[uid]) < 10:
                        self.bot_actions[uid].append(transformed_action)
                else:
                    self.bot_actions[uid] = [transformed_action]

                # Checking if enough actions are present to end turn
                if len(self.bot_actions[uid]) >= 10:
                    player.end_turn()
                    turn_ended = GameSystem.do_turn(self.bot_actions)

                    # If all bot actions have ended, empty the action list
                    if turn_ended:
                        self.bot_actions = {}
            if invalid_action:
                GameSystem.players[uid].invalid_action = True
            else:
                GameSystem.players[uid].invalid_action = False
            return self.observation(uid)


        def _get_player(self, uid):
            return GameSystem.players[uid]

        def _param_to_uid(self, param):
            uids = list(GameSystem.players)

            if param in uids:
                return uids[param]
            return -1

        def _param_to_mid(self, param):
            mids = list(GameSystem.food_market)

            if param in mids:
                return mids[param]
            return -1

        def _param_to_skill(self, param):
            skills = list(GameSystem.skill_votes)

            if param in skills:
                return skills[param]
            return -1

        def _param_to_food_vote(self, param):
            food_votes = list(GameSystem.food_votes)

            if param in food_votes:
                return food_votes[param]
            return -1

        def _int_to_actions(self, i):
            action = 1
            actions = self.actions
            action_list = list(actions)

            temp = np.prod(actions[action_list[0]])

            # Preventing over and underflow
            if i > self.action_boundary:
                i = self.action_boundary
            elif i < 0:
                i = 0
            # Choosing which action is being taken
            while temp < i:
                # Making sure action does not overflow
                if action >= len(action_list):
                    action = 0

                add_to_temp = np.prod(actions[action_list[action]])
                temp += add_to_temp
                action += 1

            action -= 1
            temp -= np.prod(actions[action_list[action]])

            params_temp = i - temp
            params = self._decode_params(params_temp, 100)
            return [action, *params]

        def _decode_params(self, i, max_index):
            # The last parameter changes only when first and second have exhausted their combinations
            # TODO Make sure the third parameter does not go over max_index
            third = math.ceil(i / max_index ** 2)

            # To simplify further lines, coeff is used to standardise the input so that the parameter is always <= max_index
            coeff = (third - 1) * max_index ** 2
            # The normalising the input so that the parameter is <= max_index
            # The second param changes only when first parameter has exhausted combinations
            second = math.ceil((i - coeff) / max_index)
            # Further normalising so that the output is <= to the max index
            first = math.ceil(i - ((second - 1) * max_index + coeff))

            return [first, second, third]

        def _get_boundaries(self, write=False):
            action_list = list(self.actions)
            boundary = 0
            for i in range(len(list(self.actions))):
                if write:
                    print(action_list[i], "\t", boundary + 1, "\t", boundary + np.prod(self.actions[action_list[i]]))
                boundary += np.prod(self.actions[action_list[i]])
            return boundary

        def _coin_percentage(self, param):
            coins = math.ceil(param / 100 * self.player.coins)
            return coins

        def _energy_percentage(self, param):
            energy = math.ceil(param / 100 * self.player.energy)
            return energy

    class PublicAPI:
        """
        API to be used by human players.
        Will provide an abstraction for REST api and outputs JSON objects of data
        """