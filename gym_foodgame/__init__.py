from gym.envs.registration import register

register(
    id='gym_foodgame-v0',
    entry_point='gym_foodgame.envs:FoodGameEnv',
)