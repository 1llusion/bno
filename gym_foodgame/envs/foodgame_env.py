import gym
from gym import spaces
import numpy as np
from scipy import stats
from random import randint
from bno_system import GameAPI
from bno_system import GameSystem


class FoodGameEnv(gym.Env):
  metadata = {'render.modes': ['human']}
  player_model = None # Set this externally
  all_scores = [] # Rewards of other players
  game_results = [] # When rendering, bots ranking is appended here
  turn = 1 # Counts actions in a turn 0 - 9

  enemy_model = None

  def __init__(self):
    api = GameAPI.BotAPI()
    glob_max = np.finfo(np.float32).max
    glob_min = np.finfo(np.float32).min

    self.action_space = spaces.Box(0 ,1010321, shape=(1,), dtype=np.int)

    # Observation is the state of all players
    self.observation_space = spaces.Box(glob_min, glob_max, shape=(244,), dtype=np.float32)

    # Store what the agent tried
    self.curr_episode = -1
    self.action_episode_memory = []

    self.bot_model = None

    self.action_boundary = api._get_boundaries() # Stores the action boundary
    self.action_score = 0  # 10 is maximum score that can be gained

  def reset(self):
    # Resetting game
    self.api = GameAPI.BotAPI()
    GameSystem.do_reset()
    self.players = [GameSystem.add_player() for x in range(10)]

    # Setting the player to be any of the 3
    self.player_uid = self.players[randint(0, len(self.players) - 1)]
    self.current_step = 0

    self.action_score = 0
    self.turn = 1
    return self._next_observation()

  def _next_observation(self):
    obs = self.api.observation(self.player_uid)

    return obs

  def step(self, action):
    # Making sure the actions aren't negative
    action = abs(int(action))
    observation = self._take_action(action)

    self.current_step += 1

    self.score = GameSystem.players[self.player_uid].score
    self.day = GameSystem.day
    if GameSystem.game_ended() or not GameSystem.players[self.player_uid].alive:
      done = True
    else:
      done = False

    obs = self._next_observation()

    self.all_scores = observation[-len(self.players):]  # Adding current scores so that it can be scaled between 0 and 1

    # Get ranking score (0 - 1)
    if (max(self.all_scores) - min(self.all_scores)) == 0:
      ranking_score = 0
    else:
      ranking_score = (self.score - min(self.all_scores)) / (max(self.all_scores) - min(self.all_scores))

    # Checking if action is valid
    if GameSystem.players[self.player_uid].invalid_action:
      if not self.action_score <= -10:
        bias = 10 - self.turn # Used to adjust the score. If  a wrong action in step 1, it should carry as much weight as wrong action in step 10
        self.action_score -= 1 + bias
    else:
      if self.action_score < 10:
        self.action_score += 1
    # Computing score for actions between -1 and 1
    norm_action_score = 2*(self.action_score + 10) / 20 - 1

    # Adding an extra deterrent when all actions are wrong
    if norm_action_score == -1:
      norm_action_score = -2

    # Getting final reward (note that action score and ranking score is split 50/50)
    reward = (ranking_score + norm_action_score) / 2

    # Adding a big reward hit when boundary if overstepped
    if action > self.action_boundary:
      reward -= action - self.action_boundary

    # Adding big reward if game ended and player is still alive
    if done and GameSystem.players[self.player_uid].alive:
      reward += self.score * self.day

    # Ticking over turn
    if self.turn >= 10:
      self.turn = 0
    self.turn += 1
    return obs, reward, done, {}

  def _take_action(self, action):
    other_players = self.players.copy()
    other_players.remove(self.player_uid)
    # Compete against random bots
    #GameAPI.random_mode(other_players, self.api)

    # Compete against trained bots
    GameAPI.compete_mode(self.enemy_model, other_players, self.api)

    # Compete against one random and one trained bot
    #GameAPI.nothing_mode(other_players, self.api)
    obs = self.api.do_action(self.player_uid, action)
    self.took_action = action

    return obs

  def render(self, mode='human'):
    """
    Gets ranking. star_UID used to add a star to see how the trained bot ranked
    :param star_uid:
    :return: None
    """
    self.api.observation(self.player_uid, save_to_db=True)
    if GameSystem.game_ended() or not GameSystem.players[self.player_uid].alive:
      all_scores = {}

      # Gettting all scores
      for uid in GameSystem.players:
        all_scores[uid] = GameSystem.players[uid].score

      # Sorting scores
      all_scores = {k: v for k, v in sorted(all_scores.items(), key=lambda item: item[1], reverse=True)}
      ranking = (list(all_scores).index(self.player_uid))+1
      print("Player ranked:", ranking, "with score:", all_scores[self.player_uid], "on day", GameSystem.day,
            "and ended up", "alive" if GameSystem.players[self.player_uid].alive else "dead")
      self.game_results.append(ranking)