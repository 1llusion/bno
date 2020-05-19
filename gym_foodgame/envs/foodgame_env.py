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

    self.action_space = spaces.Box(-1010321 ,1010321, shape=(1,), dtype=np.int)

    # Observation is the state of all players
    self.observation_space = spaces.Box(glob_min, glob_max, shape=(254,), dtype=np.float32)

    # Store what the agent tried
    self.curr_episode = -1
    self.action_episode_memory = []

    self.bot_model = None

    self.action_boundary = api._get_boundaries() # Stores the action boundary
    self.action_score = 0  # 10 is maximum score that can be gained
    self.game_api = GameAPI()
    self.reward = 0 # Reward added over time

  def reset(self):
    # Resetting game
    self.api = GameAPI.BotAPI()
    self.game_api = GameAPI()

    GameSystem.do_reset()
    self.players = [GameSystem.add_player() for x in range(10)]

    # Setting the player to be any of the 3
    self.player_uid = self.players[randint(0, len(self.players) - 1)]
    self.current_step = 0

    self.action_score = 0
    self.turn = 1
    self.reward = 0
    return self._next_observation()

  def _next_observation(self):
    obs = self.api.observation(self.player_uid, ver=3)

    return obs

  def step(self, action):
    # Making sure the actions aren't negative
    action = int(action)
    observation = self._take_action(action)

    self.current_step += 1

    self.score = GameSystem.players[self.player_uid].score
    self.day = GameSystem.day

    # Letting the game run beyond the actual end of the game. Teaching the bot to just survive for the longest
    done = False if GameSystem.players[self.player_uid].alive else True

    obs = self._next_observation()

    # Checking if action is valid
    if GameSystem.players[self.player_uid].invalid_action:
      if self.action_score > -3:
        bias = -3 + self.turn - 1 # Adjusting so that even first bad move results in very bad bias
        self.action_score += bias
      else:
        self.action_score = -3
    else:
      if self.action_score < 3:
        bias = 3 - self.turn + 1 # Even first good turn should have very good bias
        self.action_score += bias
      else:
        self.action_score = 3
    # Computing score for actions between -1 and 1
    norm_action_score = 2 * (self.action_score + 3) / 6 - 1
    reward = norm_action_score

    # Adding a big hit if AI overshoots the action boundary or goes negative
    if action < 0:
      reward -= abs(action)
    elif action > self.action_boundary:
      reward -= (action - self.action_boundary)

    # Add player scores when turn is up
    if self.turn >= 3:
      self.all_scores = observation[
                        -len(self.players):]  # Adding current scores so that it can be scaled between 0 and 1
      # Get ranking score (0 - 1)
      if (max(self.all_scores) - min(self.all_scores)) == 0:
        ranking_score = 0
      else:
        ranking_score = (self.score - min(self.all_scores)) / (max(self.all_scores) - min(self.all_scores))

      # Adjusting long-term ranking score to track progress over time
      self.reward = (self.reward + ranking_score) / 2 * self.day / 100

      # Getting final reward
      reward = self.reward + norm_action_score

      # Adding big reward if game ended and player is still alive
      if GameSystem.players[self.player_uid].alive and not done:
        reward += self.score * self.day

      # Ticking over turn
      self.turn = 0
      self.action_score = 0 #Resetting action score for next round
    self.turn += 1
    return obs, reward, done, {}

  def _take_action(self, action):
    other_players = self.players.copy()
    other_players.remove(self.player_uid)
    # Compete against random bots
    #GameAPI.random_mode(other_players, self.api)

    # Compete against trained bots
    self.game_api.compete_mode(self.enemy_model, other_players, self.api)

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
    self.api.observation(self.player_uid, save_to_db=True, ver=3)
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