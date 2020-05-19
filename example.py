import numpy as np
import gym
import datetime

import tensorflow as tf
from tensorflow.keras.models import Sequential, Model, load_model
from tensorflow.keras.layers import Dense, Activation, Flatten, Input, Concatenate
from tensorflow.keras.optimizers import Adam
from tensorflow.python.framework.ops import disable_eager_execution

from rl.agents import DDPGAgent
from rl.memory import SequentialMemory
from rl.random import OrnsteinUhlenbeckProcess

from scipy import stats
from configparser import ConfigParser
import os.path

WINDOW_SIZE = 40

# Setting and reading configuration file
config = ConfigParser()
if not os.path.exists('config.ini'):
    config.read('config.ini')
    config.add_section('main')
    config.set('main', 'iteration', "0")
    config.set('main', 'previous_average', "1000000")

    with open('config.ini', 'w') as f:
        config.write(f)

config.read('config.ini')
iteration = int(config.get('main', 'iteration'))
prev_avg = float(config.get('main', 'previous_average'))
#hllDll = ctypes.WinDLL("C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v10.0\\bin\\cudart64_100.dll")

disable_eager_execution()

print("Using GPU:", tf.test.is_gpu_available(cuda_only=True))

ENV_NAME = 'gym_foodgame:gym_foodgame-v0'


# Get the environment and extract the number of actions.
env = gym.make(ENV_NAME)
np.random.seed(123)
env.seed(123)

assert len(env.action_space.shape) == 1
nb_actions = env.action_space.shape[0]

action_input = None
def build_network():
    global action_input
    # Next, we build a very simple model.
    actor = Sequential()
    actor.add(Flatten(input_shape=(WINDOW_SIZE,) + env.observation_space.shape))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(1000))
    actor.add(Activation('relu'))
    actor.add(Dense(nb_actions))
    actor.add(Activation('linear'))
    #print(actor.summary())

    action_input = Input(shape=(nb_actions,), name='action_input')
    observation_input = Input(shape=(WINDOW_SIZE,) + env.observation_space.shape, name='observation_input')
    flattened_observation = Flatten()(observation_input)
    x = Concatenate()([action_input, flattened_observation])
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1000)(x)
    x = Activation('relu')(x)
    x = Dense(1)(x)
    x = Activation('linear')(x)
    critic = Model(inputs=[action_input, observation_input], outputs=x)
    #print(critic.summary())

    return actor, critic

# Model to be trained
model_actor, model_critic = build_network()

if os.path.exists("model_" + str(iteration) + "_actor.h5"):
    print("model_" + str(iteration) + "_actor.h5", "and", "model_" + str(iteration) + "_critic.h5",
          "weights loaded.")
    model_actor.load_weights("model_" + str(iteration) + "_actor.h5")
    model_critic.load_weights("model_" + str(iteration) + "_critic.h5")

memory = SequentialMemory(limit=1000000, window_length=WINDOW_SIZE)
random_process = OrnsteinUhlenbeckProcess(size=nb_actions, theta=.15, mu=0., sigma=.3)
agent = DDPGAgent(nb_actions=nb_actions, actor=model_actor, critic=model_critic, critic_action_input=action_input,
                  memory=memory, nb_steps_warmup_critic=1000, nb_steps_warmup_actor=1000,
                  random_process=random_process, gamma=1, target_model_update=0.001)
agent.compile(Adam(lr=.001, clipnorm=.01), metrics=['mae'])

rounds = 1
while rounds <= 10:
    if iteration > 0:
        player_actor = load_model("model_" + str(iteration) + ".h5")
        print("Competing against", "model_" + str(iteration) + ".h5")
        env.enemy_model = player_actor

    agent.fit(env, nb_steps=10000, visualize=False, verbose=3, nb_max_episode_steps=1000)

    agent.test(env, nb_episodes=10, visualize=True, nb_max_episode_steps=1000)

    curr_avg = sum(env.game_results) / len(env.game_results)
    print("Current average:", curr_avg)
    if curr_avg <= prev_avg:
        print("Model performed better, updating model")

        iteration += 1

        model_actor.save("model_" + str(iteration) + ".h5", overwrite=True)
        model_critic.save("critic_" + str(iteration) + ".h5", overwrite=True)
        agent.save_weights('model_' + str(iteration) + '.h5', overwrite=True)

        prev_results = env.game_results
        prev_avg = curr_avg

        print("Writing config file")
        config.read('config.ini')
        config.set('main', 'iteration', str(iteration))
        config.set('main', 'previous_average', str(prev_avg))

        with open('config.ini', 'r+') as f:
            config.write(f)

        print("Done")

    rounds += 1

agent.save_weights('model_' + str(iteration) + '.h5', overwrite=True)
print("Done!")
# What I am looking for is DDPG
# https://github.com/inoryy/reaver
# https://github.com/inoryy/reaver
# https://arxiv.org/abs/1810.06394

# TODO Save both Actor and Critic weights
# TODO Load Actor and Critic weights to continue training