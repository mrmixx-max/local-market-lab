"""Reinforcement Learning for Trading — pure Python + numpy.
Algorithms: q_learning_trading, dqn_trading, policy_gradient, rl_forecast.
Action space: {Buy, Sell, Hold}.  Reward: P&L per step.
"""

from __future__ import annotations

import random

import numpy as np

ACTIONS = ["Buy", "Sell", "Hold"]
N_ACT = 3


def _returns(data: np.ndarray) -> np.ndarray:
    """Compute simple returns from a price series: r[t] = p[t]/p[t-1] - 1."""
    return data[1:] / data[:-1] - 1.0


def _disc(ret: float, n: int = 5, clip: float = 0.03) -> int:
    """Discretize a return into n bins in [-clip, clip]. Returns int in [0, n-1]."""
    raw = int((np.clip(ret, -clip, clip) + clip) / (2 * clip / n))
    return min(raw, n - 1)  # guard against edge case where ret == clip exactly


def _svec(t: int, pos: int, rets: np.ndarray) -> np.ndarray:
    """State vector: one-hot position(3) + normalised return + momentum."""
    mom = np.mean(rets[max(0, t - 4) : t + 1]) if t > 0 else 0.0
    return np.array([float(i == pos) for i in range(3)] + [rets[t] * 10, mom * 10])


def q_learning_trading(
    data: list[float],
    episodes: int = 500,
    alpha: float = 0.1,
    gamma: float = 0.95,
    epsilon: float = 0.1,
) -> dict:
    """Tabular Q-Learning: state=(pos, market-bin), reward=P&L."""
    prices = np.array(data, dtype=float)
    rets = _returns(prices)
    n = len(rets)
    if n < 10:
        raise ValueError("need ≥11 price points")
    nb = 5
    Q = np.zeros((3 * nb, N_ACT))
    rng = random.Random(42)
    rewards = []
    for _ in range(episodes):
        pos, ep_r = 1, 0.0
        for t in range(n - 1):
            mkt = _disc(rets[t], nb)
            st = pos * nb + mkt
            act = (
                rng.randrange(N_ACT)
                if rng.random() < epsilon
                else int(np.argmax(Q[st]))
            )
            new_pos = 1 if act == 0 else (2 if act == 1 else pos)
            r = (1 if new_pos == 1 else (-1 if new_pos == 2 else 0)) * rets[t + 1]
            ep_r += r
            nm = _disc(rets[t + 1], nb) if t + 2 < n else mkt
            ns = new_pos * nb + nm
            Q[st, act] += alpha * (r + gamma * np.max(Q[ns]) - Q[st, act])
            pos = new_pos
        rewards.append(ep_r)
    return {
        "algorithm": "q_learning",
        "episodes": episodes,
        "final_reward": round(rewards[-1], 4),
        "avg_reward": round(sum(rewards) / len(rewards), 4),
        "forecast": rl_forecast(data, min(30, n)),
    }


def dqn_trading(data: list[float], episodes: int = 500, hidden_size: int = 64) -> dict:
    """Deep Q-Network w/ experience replay + target network."""
    prices = np.array(data, dtype=float)
    rets = _returns(prices)
    n = len(rets)
    if n < 20:
        raise ValueError("need ≥21 price points")
    sd, gamma, lr, eps = 5, 0.95, 0.01, 0.1
    rng = np.random.default_rng(42)
    W1 = rng.normal(0, np.sqrt(2.0 / sd), (sd, hidden_size))
    b1 = np.zeros(hidden_size)
    W2 = rng.normal(0, np.sqrt(2.0 / hidden_size), (hidden_size, N_ACT))
    b2 = np.zeros(N_ACT)
    W1t, b1t, W2t, b2t = W1.copy(), b1.copy(), W2.copy(), b2.copy()
    buf, rewards = [], []

    def fw(s, W1_, b1_, W2_, b2_):
        h = np.maximum(0, s @ W1_ + b1_)
        return h @ W2_ + b2_, h

    for ep in range(episodes):
        pos, ep_r = random.randrange(3), 0.0
        for t in range(n - 1):
            s = _svec(t, pos, rets)
            act = (
                random.randrange(N_ACT)
                if random.random() < eps
                else int(np.argmax(fw(s, W1, b1, W2, b2)[0]))
            )
            new_pos = act if act < 2 else pos
            r = (1 if new_pos == 1 else (-1 if new_pos == 2 else 0)) * rets[t + 1]
            ep_r += r
            buf.append((s, act, r, _svec(t + 1, new_pos, rets)))
            pos = new_pos
        if len(buf) >= 16:
            for s, act, r, sn in random.sample(buf, 16):
                tgt = r + gamma * np.max(fw(sn, W1t, b1t, W2t, b2t)[0])
                qp, h = fw(s, W1, b1, W2, b2)
                dq = qp.copy()
                dq[act] = 2 * (qp[act] - tgt)
                dh = (dq @ W2.T) * (h > 0).astype(float)
                W1 -= lr * np.outer(s, dh)
                b1 -= lr * dh
                W2 -= lr * np.outer(h, dq)
                b2 -= lr * dq
        if ep % 50 == 0:
            W1t, b1t, W2t, b2t = W1.copy(), b1.copy(), W2.copy(), b2.copy()
        rewards.append(ep_r)
    return {
        "algorithm": "dqn",
        "episodes": episodes,
        "final_reward": round(rewards[-1], 4),
        "avg_reward": round(sum(rewards) / len(rewards), 4),
        "forecast": rl_forecast(data, min(30, n)),
    }


def policy_gradient(data: list[float], episodes: int = 500) -> dict:
    """REINFORCE: softmax policy network, discounted reward baseline."""
    prices = np.array(data, dtype=float)
    rets = _returns(prices)
    n = len(rets)
    if n < 20:
        raise ValueError("need ≥21 price points")
    sd, hidden, lr, gamma = 5, 32, 0.01, 0.95
    rng = np.random.default_rng(42)
    W1 = rng.normal(0, 0.1, (sd, hidden))
    b1 = np.zeros(hidden)
    W2 = rng.normal(0, 0.1, (hidden, N_ACT))
    b2 = np.zeros(N_ACT)
    rewards = []

    def sm(x):
        e = np.exp(x - np.max(x))
        return e / e.sum()

    for _ in range(episodes):
        pos, traj = random.randrange(3), []
        for t in range(n - 1):
            s = _svec(t, pos, rets)
            h = np.maximum(0, s @ W1 + b1)
            act = int(np.random.choice(N_ACT, p=sm(h @ W2 + b2)))
            new_pos = act if act < 2 else pos
            r = (1 if new_pos == 1 else (-1 if new_pos == 2 else 0)) * rets[t + 1]
            traj.append((s, act, r))
            pos = new_pos
        G, run = [], 0.0
        for _, _, r in reversed(traj):
            run = r + gamma * run
            G.insert(0, run)
        G = np.array(G)
        if G.std() > 1e-8:
            G = (G - G.mean()) / G.std()
        for (s, act, _), g in zip(traj, G):
            h = np.maximum(0, s @ W1 + b1)
            p = sm(h @ W2 + b2)
            dlog = -p.copy()
            dlog[act] += 1.0
            dlog *= g
            dh = (dlog @ W2.T) * (h > 0).astype(float)
            W1 += lr * np.outer(s, dh)
            b1 += lr * dh
            W2 += lr * np.outer(h, dlog)
            b2 += lr * dlog
        rewards.append(sum(r for _, _, r in traj))
    return {
        "algorithm": "policy_gradient",
        "episodes": episodes,
        "final_reward": round(rewards[-1], 4),
        "avg_reward": round(sum(rewards) / len(rewards), 4),
        "forecast": rl_forecast(data, min(30, n)),
    }


def rl_forecast(data: list[float], horizon: int = 30) -> dict:
    """Train Q-Learning greedily, then predict optimal actions for horizon."""
    prices = np.array(data, dtype=float)
    rets = _returns(prices)
    n = len(rets)
    if n < 10:
        raise ValueError("need ≥11 price points")
    nb = 5
    Q = np.zeros((3 * nb, N_ACT))
    rng = random.Random(42)
    for _ in range(200):
        pos = 1
        for t in range(n - 1):
            mkt = _disc(rets[t], nb)
            st = pos * nb + mkt
            act = rng.randrange(N_ACT) if rng.random() < 0.1 else int(np.argmax(Q[st]))
            new_pos = 1 if act == 0 else (2 if act == 1 else pos)
            r = (1 if new_pos == 1 else (-1 if new_pos == 2 else 0)) * rets[t + 1]
            nm = _disc(rets[t + 1], nb) if t + 2 < n else mkt
            Q[st, act] += 0.1 * (r + 0.95 * np.max(Q[new_pos * nb + nm]) - Q[st, act])
            pos = new_pos
    h = min(horizon, n - 1)
    pos, actions, equity = 1, [], [1.0]
    for t in range(n - 1 - h, n - 1):
        act = int(np.argmax(Q[pos * nb + _disc(rets[t], nb)]))
        new_pos = 1 if act == 0 else (2 if act == 1 else pos)
        r = (1 if new_pos == 1 else (-1 if new_pos == 2 else 0)) * rets[t + 1]
        actions.append(ACTIONS[act])
        equity.append(equity[-1] * (1 + r))
        pos = new_pos
    return {
        "actions": actions,
        "equity_curve": [float(round(v, 4)) for v in equity],
        "final_position": ACTIONS[pos] if pos < 2 else "Hold",
        "horizon": h,
    }
