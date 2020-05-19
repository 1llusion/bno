import uuid
import math
from random import randint
import logging
from collections import deque

class GameSystem:
    players = {}
    dead_players = 0
    food_requirement = 0
    day = 1

    global_min_bid = 1  # Minimum starting bid food price
    global_max_bid = 1  # Maximum starting bid food price
    food_bids = {}
    food_market = {}

    food_votes = {"increase_min_bid": 0,
                  "decrease_min_bid": 0,
                  "increase_max_bid": 0,
                  "decrease_max_bid": 0
                 }

    skill_bids = {}
    skill_votes = {"min_bid_skill": 0,
                   "max_bid_skill": 0,
                   "energy_skill": 0,
                   "money_conversion_skill": 0,
                   "food_conversion_skill": 0,
                   "auction_skill": 0, }
    skill_auction = "food_conversion_skill"    # Skill on auction

    @classmethod
    def add_player(cls, username=False):
        uid = str(uuid.uuid4()) if not username else username
        player_num = 1 # If Username exists, increase number to be added after their username
        while uid in cls.players:
            uid = str(uuid.uuid4()) if not username else str(username) + "-" + str(player_num)
            player_num += 1

        cls.players[uid] = Player(uid)
        return uid


    @classmethod
    def do_turn(cls, action_list):
        """
        :param action_list: Dict of lists {uid: [actions]}
        :return:
        """
        # Checking if all players ended their turn
        all_turns_ended = []
        for uid in cls.players:
            all_turns_ended.append(cls.players[uid].turn_ended)

        if False in all_turns_ended:
            return False

        # Re-setting the votes from past turn
        for skill in cls.skill_votes:
            cls.skill_votes[skill] = 0

        # Re-setting votes from past food votes
        for vote in cls.food_votes:
            cls.food_votes[vote] = 0

        priorities = cls._get_priorities()
        for uid in priorities:
            # Resetting player priority
            cls.players[uid].turn_priority = 0
            success = cls._do_actions(uid, action_list[uid])

        # Sorting out markets
        success = cls._do_market_auctions()
        if not success:
            print("REEEEE")

        # Skill Auction
        cls._do_skill_auction()

        # Min/max food vote auction
        cls._do_food_votes()

        # System maintenance
        rand_day = randint(1, cls.day)
        cls.food_requirement = math.ceil((rand_day ** math.log10(cls.day)) / rand_day)
        cls.day += 1

        # Allowing players to resume with their turns
        for uid in cls.players:
            cls.players[uid].turn_ended = False

        return True

    @classmethod
    def game_ended(cls):
        if cls.dead_players >= len(cls.players) - 1:
            return True
        return False

    @classmethod
    def do_reset(cls):
        # Resetting system
        cls.players = {}
        cls.dead_players = 0
        cls.food_requirement = 0
        cls.day = 1

        cls.global_min_bid = 1  # Minimum starting bid food price
        cls.global_max_bid = 1  # Maximum starting bid food price
        cls.food_bids = {}
        cls.food_market = {}

        cls.skill_bids = {}
        cls.skill_votes = {"min_bid_skill": 0,
                           "max_bid_skill": 0,
                           "energy_skill": 0,
                           "money_conversion_skill": 0,
                           "food_conversion_skill": 0,
                           "auction_skill": 0}
        cls.skill_auction = "food_conversion_skill"

    @classmethod
    def _get_priorities(cls):
        # First get all priorities
        priorities = {}
        for player in cls.players:
            priority_exists = randint(0, 1)  # Randomly choose if priority will be added or taken away
            new_priority = [-0.01, 0.01]  # Priority to be added or taken away
            while cls.players[player].turn_priority in priorities:
                """
                If two players have the same priority,
                    randomly add, remove a priority until they have a unique priority.
                    Decimal numbers are used to:
                        a) not change the resulting priority too high/low
                        b) give a buffer space between whole priorities
                """
                cls.players[player].turn_priority += new_priority[priority_exists]
            priorities[cls.players[player].turn_priority] = cls.players[player].uid
            # Clearing players priority
            cls.players[player].turn_priority = 0

        #Swapping keys and values
        priorities = {value: key for key, value in priorities.items()}
        #Ordering priorities
        priorities = {k: v for k, v in sorted(priorities.items(), key=lambda item: item[1], reverse=True)}
        # Turning priorities into a list and performing actual turn
        priorities_lst = list(priorities)
        return priorities_lst

    @classmethod
    def _get_market_priorities(cls):
        priorities = list(cls.food_bids)
        priorities.sort()

        return priorities

    @classmethod
    def _do_market_auctions(cls):
        success = True
        market_priorities = cls._get_market_priorities()
        markets_for_removal = []
        try:
            for market_priority in market_priorities:
                # Looping through markets
                for mid in cls.food_bids[market_priority]:
                    auction = cls.food_market[mid]
                    highest_bid = {"bid": auction['start_bid'],
                                   "uid": False}
                    for uid in cls.food_bids[market_priority][mid]:
                        # Adding bids
                        if highest_bid['bid'] < cls.food_bids[market_priority][mid][uid] <= cls.players[uid].food:
                            highest_bid['bid'] = cls.food_bids[market_priority][mid][uid]
                            highest_bid['uid'] = uid

                    # A person won the bid
                    if highest_bid['uid']:
                        cls.players[highest_bid['uid']].food += auction['amount']
                        cls.players[highest_bid['uid']].coins -= highest_bid['bid']
                        # Adding money to auction winner
                        cls.players[auction['uid']].coins += highest_bid['bid']
                        # Deleting auction
                        markets_for_removal.append(mid)

            for mid in markets_for_removal:
                del cls.food_market[mid]
        except:
            success = False
        return success

    @classmethod
    def _do_skill_auction(cls):
        # Skill Auction
        max_bid = {'uid': False,
                   'bid': 0}
        for uid in cls.skill_bids:
            if max_bid['bid'] < cls.skill_bids[uid] <= cls.players[uid].coins:
                max_bid['bid'] = cls.skill_bids[uid]
                max_bid['uid'] = uid

        # Making sure an auction is actually taking place
        if max_bid['uid'] and cls.skill_auction:
            cls.players[max_bid['uid']].skill[cls.skill_auction] += 1
            cls.players[max_bid['uid']].coins -= max_bid['bid']

            # Distributing money to people with "auction_skill"
            total_auction_skills = 0
            players_to_receive_auction_coins = {}
            for uid in cls.players:
                if cls.players[uid].skill['auction_skill'] and uid not in cls.skill_bids:
                    total_auction_skills += cls.players[uid].skill['auction_skill']
                    # Adding uid so the player can receive their money
                    players_to_receive_auction_coins[uid] = cls.players[uid].skill['auction_skill']

            for uid in players_to_receive_auction_coins:
                cls.players['uid'].coins += int(cls.players[uid].skill['auction_skill'] / total_auction_skills \
                                                * max_bid['bid'])

        # Adding next skill for auction
        highest_vote = 0
        for skill in cls.skill_votes:
            if cls.skill_votes[skill] > highest_vote:
                cls.skill_auction = skill
                highest_vote = cls.skill_votes[skill]

    @classmethod
    def _do_actions(cls, uid, action_list):
        """
        Do actions per player.
        :param action_list: Actions for one player
        :return: Boolean -> Has the action executed successfully?
        """
        player = cls.players[uid]
        result = False
        if not player.alive:
            return False

        # Executing actions
        for action in action_list:
            result = getattr(player, action['name'])(*action['params'])
            if not result:
                #logging.error(action['name'] + "failed to execute with params:" + str(*action['params']))
                pass

        return result

    @classmethod
    def _do_food_votes(cls):
        max_vote = {'votes': 0,
                    'type': False}
        for vote in cls.food_votes:
            if cls.food_votes[vote] > max_vote['votes']:
                max_vote['votes'] = cls.food_votes[vote]
                max_vote['type'] = vote

        if max_vote['type'] == "increase_min_bid":
            cls.global_min_bid += 1
        elif max_vote['type'] == "decrease_min_bid" and cls.global_min_bid > 0:
            cls.global_min_bid -= 1
        elif max_vote['type'] == "increase_max_bid":
            cls.global_max_bid += 1
        elif max_vote['type'] == "decrease_max_bid" and cls.global_max_bid > 0:
            cls.global_max_bid -= 1


class Player:
    # Basic variables
    food = 10
    energy = 1
    coins = 0

    # Utility variables
    alive = True
    score = 0

    turn_priority = 0
    turn_ended = False
    invalid_action = False  # Tracking whether a player took an invalid action

    def __init__(self, uid):
        self.uid = uid

        # Skills, expressed in %/100 (1 = 100%)
        self.skill = {"min_bid_skill": 1,
                      "max_bid_skill": 1,
                      "energy_skill": 1,
                      "money_conversion_skill": 1,
                      "food_conversion_skill": 1,
                      "auction_skill": 0}

        self.action_memory = deque([0] * 20)

    #   Utility methods
    def _end_turn(self):
        """
        Maintenance when turn has ended
        :return:
        """
        self.food -= GameSystem.food_requirement
        self.alive = True if self.food >= 0 else False

        if not self.alive:
            GameSystem.dead_players += 1

    def _get_min_max_food_bid(self):
        return GameSystem.global_min_bid * self.skill['min_bid_skill'], GameSystem.global_max_bid * self.skill['max_bid_skill']

    # Actions
    def end_turn(self):
        self._end_turn()
        self.score += (self.coins + self.food) * (GameSystem.day + 1)
        self.turn_ended = True

    def energy_to_coins(self, amount):
        """
        Converts "amount" of energy to coins
        :param amount:
        :return:
        """
        if self.energy - amount <= 0 or amount == 0:
            return False

        self.coins += (2 * amount - 1) * self.skill['money_conversion_skill']
        self.energy -= amount
        return True

    def energy_to_food(self, amount):
        if self.energy - amount < 0 or amount == 0:
            return False

        self.food += (2 * amount - 1) * self.skill['food_conversion_skill']
        self.energy -= amount
        return True

    def add_to_market(self, amount, start_bid):
        """
        Creates a market auction for food.
        Price is starting bid per unit
        :param start_bid:
        :param amount:
        :return:
        """
        min_bid, max_bid = self._get_min_max_food_bid()
        if self.food - amount < 0 or start_bid < min_bid or start_bid > max_bid or len(GameSystem.food_market) >= 100:
            return False

        GameSystem.food_market[str(uuid.uuid4())] = {"amount": amount, "start_bid": start_bid, "uid": self.uid}
        return True

    # Voting actions
    def add_bid_for_food(self, mid, bid, priority):
        """
        Add a bid for food in a market with certain priority.
        The bid is per food item, therefore the total cost is amount * bid
        :param bid:
        :param priority:
        :param mid: market id
        :return:
        """
        if bid > self.coins:
            return False

        if mid not in list(GameSystem.food_market):
            return False

        if priority not in GameSystem.food_bids:
            GameSystem.food_bids[priority] = {}
        if mid not in GameSystem.food_bids[priority]:
            GameSystem.food_bids[priority][mid] = {}

        GameSystem.food_bids[priority][mid][self.uid] = bid
        return True

    def add_food_vote(self, vote):
        """
        Votes whether global min/max food bid should be increased/decreased
        :param vote:
        :return:
        """
        if vote not in GameSystem.food_votes:
            return False

        GameSystem.food_votes[vote] += 1

    def add_bid_for_skill_auction(self, bid):
        if bid > self.coins:
            return False

        GameSystem.skill_bids[self.uid] = bid

    def add_vote_for_skill_auction(self, skill):
        if skill not in GameSystem.skill_votes:
            return False

        GameSystem.skill_votes[skill] += 1

    def add_vote_for_turn(self, uid):
        if uid not in GameSystem.players:
            return False

        GameSystem.players[uid].turn_priority += 1

    def do_nothing(self, x):
        pass
