"""Evolutionary algorithms for feature selection and hyperparameter tuning.
Pure numpy: genetic_feature_selection (binary GA), genetic_hyperparameter_tuning
(discrete GA), differential_evolution (DE/rand/1/bin), nsga2_multi_objective."""
from __future__ import annotations
from typing import Any, Callable
import numpy as np


def _kfold(n, k=5, seed=42):
    """Generate k-fold train/test index splits without shuffling within folds."""
    rng = np.random.RandomState(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, k)
    for i in range(k):
        yield np.concatenate([folds[j] for j in range(k) if j != i]), folds[i]


def _rmse(y, p):
    """Root mean squared error between actual y and predicted p."""
    return float(np.sqrt(np.mean((y - p) ** 2)))


def genetic_feature_selection(data, target, pop_size=50, generations=100, seed=42):
    """Binary GA for optimal feature subset selection. Returns mask + RMSE."""
    rng = np.random.RandomState(seed)
    n_s, n_f = data.shape

    def fitness(mask):
        if mask.sum() == 0:
            return float("inf")
        X = data[:, mask.astype(bool)]
        errs = []
        for tr, va in _kfold(n_s, seed=seed):
            Xtr, ytr, Xva, yva = X[tr], target[tr], X[va], target[va]
            A = Xtr.T @ Xtr + 1e-3 * np.eye(Xtr.shape[1])
            try:
                w = np.linalg.solve(A, Xtr.T @ ytr)
            except np.linalg.LinAlgError:
                return float("inf")
            errs.append(_rmse(yva, Xva @ w))
        return float(np.mean(errs))

    pop = rng.randint(0, 2, size=(pop_size, n_f))
    best_mask, best_score = pop[0].copy(), float("inf")
    for _ in range(generations):
        scores = np.array([fitness(ind) for ind in pop])
        bi = np.argmin(scores)
        if scores[bi] < best_score:
            best_score, best_mask = scores[bi], pop[bi].copy()
        pop = np.array([pop[a if scores[a] < scores[b] else b].copy()
                        for _ in range(pop_size)
                        for a, b in [rng.choice(pop_size, 2, replace=False)]])
        for i in range(0, pop_size - 1, 2):
            m = rng.random(n_f) < 0.5
            pop[i, m], pop[i + 1, m] = pop[i + 1, m].copy(), pop[i, m].copy()
        pop = np.where(rng.random((pop_size, n_f)) < 0.05, 1 - pop, pop)
    selected = np.where(best_mask == 1)[0].tolist()
    return {"selected_features": selected, "n_features": len(selected),
            "rmse": round(best_score, 6), "mask": best_mask.tolist()}


def genetic_hyperparameter_tuning(data, target, model_fn, param_space,
                                   pop_size=30, generations=50, seed=42):
    """GA over discrete param space. model_fn(X_tr,y_tr,X_va,y_va,**p) -> rmse."""
    rng = np.random.RandomState(seed)
    n_s = len(data)
    keys = list(param_space.keys())

    def fitness(ind):
        try:
            return float(np.mean([model_fn(data[tr], target[tr], data[va], target[va], **ind)
                                  for tr, va in _kfold(n_s, seed=seed)]))
        except Exception:
            return float("inf")

    pop = [{k: rng.choice(param_space[k]) for k in keys} for _ in range(pop_size)]
    best_ind, best_score = pop[0], float("inf")
    for _ in range(generations):
        scores = [fitness(ind) for ind in pop]
        bi = int(np.argmin(scores))
        if scores[bi] < best_score:
            best_score, best_ind = scores[bi], pop[bi].copy()
        pop = [pop[a].copy() if scores[a] < scores[b] else pop[b].copy()
               for _ in range(pop_size)
               for a, b in [rng.choice(pop_size, 2, replace=False)]]
        for i in range(0, pop_size - 1, 2):
            if rng.random() < 0.8:
                for k in keys[:rng.randint(len(keys)) + 1]:
                    pop[i][k], pop[i + 1][k] = pop[i + 1][k], pop[i][k]
        for ind in pop:
            if rng.random() < 0.15:
                km = rng.choice(keys)
                ind[km] = rng.choice(param_space[km])
    return {"best_params": best_ind, "rmse": round(best_score, 6),
            "param_space": {k: len(v) for k, v in param_space.items()}}


def differential_evolution(data, target, model_fn, param_space,
                            pop_size=30, generations=50, F=0.8, CR=0.9, seed=42):
    """DE/rand/1/bin for continuous params. model_fn(X_tr,y_tr,X_va,y_va,**p) -> rmse."""
    rng = np.random.RandomState(seed)
    n_s = len(data)
    keys = list(param_space.keys())
    bounds = np.array([param_space[k] for k in keys])
    lo, hi = bounds[:, 0], bounds[:, 1]

    def fitness(x):
        params = {k: float(np.clip(x[i], lo[i], hi[i])) for i, k in enumerate(keys)}
        try:
            return float(np.mean([model_fn(data[tr], target[tr], data[va], target[va], **params)
                                  for tr, va in _kfold(n_s, seed=seed)]))
        except Exception:
            return float("inf")

    pop = lo + rng.rand(pop_size, len(keys)) * (hi - lo)
    scores = np.array([fitness(ind) for ind in pop])
    bi = np.argmin(scores)
    best, best_score = pop[bi].copy(), scores[bi]
    for _ in range(generations):
        for i in range(pop_size):
            a, b, c = pop[rng.choice([j for j in range(pop_size) if j != i], 3, replace=False)]
            cross = rng.rand(len(keys)) < CR
            cross[rng.randint(len(keys))] = True
            trial = np.where(cross, np.clip(a + F * (b - c), lo, hi), pop[i])
            s = fitness(trial)
            if s <= scores[i]:
                pop[i], scores[i] = trial, s
                if s < best_score:
                    best, best_score = trial.copy(), s
    return {"best_params": {k: round(float(best[i]), 6) for i, k in enumerate(keys)},
            "rmse": round(float(best_score), 6)}


def nsga2_multi_objective(data, target, model_fn, param_space,
                           pop_size=30, generations=50, seed=42):
    """NSGA-II minimising (rmse, complexity). model_fn -> (rmse, complexity)."""
    rng = np.random.RandomState(seed)
    n_s = len(data)
    keys = list(param_space.keys())
    bounds = np.array([param_space[k] for k in keys])
    lo, hi = bounds[:, 0], bounds[:, 1]
    nk = len(keys)

    def evaluate(x):
        params = {k: float(np.clip(x[i], lo[i], hi[i])) for i, k in enumerate(keys)}
        try:
            pairs = [model_fn(data[tr], target[tr], data[va], target[va], **params)
                     for tr, va in _kfold(n_s, seed=seed)]
            return float(np.mean([p[0] for p in pairs])), float(np.mean([p[1] for p in pairs]))
        except Exception:
            return float("inf"), float("inf")

    def nds(objs):
        """Non-dominated sorting — vectorized with numpy.

        Returns a list of fronts, where each front is a list of
        indices into objs that belong to that Pareto front.
        """
        n = len(objs)
        # Vectorized dominance check: dom[i,j] = True if i dominates j
        # objs is (n, n_obj)
        le = objs[:, None, :] <= objs[None, :, :]  # (n, n, n_obj)
        lt = objs[:, None, :] < objs[None, :, :]   # (n, n, n_obj)
        dom = np.all(le, axis=2) & np.any(lt, axis=2)  # (n, n)
        # S[i] = set of individuals dominated by i
        # n_dom[i] = number of individuals that dominate i
        n_dom = dom.sum(axis=0)  # (n,)
        S = [set(np.where(dom[i])[0]) for i in range(n)]
        remaining = set(range(n))
        fronts = []
        while remaining:
            front = [i for i in remaining if n_dom[i] == 0]
            fronts.append(front)
            remaining -= set(front)
            for i in front:
                for j in S[i]:
                    n_dom[j] -= 1
        return fronts

    def crowding(objs, front):
        if len(front) <= 2:
            return np.full(len(front), float("inf"))
        f, d = objs[front], np.zeros(len(front))
        for m in range(f.shape[1]):
            o = np.argsort(f[:, m])
            d[o[0]] = d[o[-1]] = float("inf")
            r = f[o[-1], m] - f[o[0], m]
            if r > 0:
                for k in range(1, len(front) - 1):
                    d[o[k]] += (f[o[k + 1], m] - f[o[k - 1], m]) / r
        return d

    pop = lo + rng.rand(pop_size, nk) * (hi - lo)
    objs = np.array([evaluate(ind) for ind in pop])
    for _ in range(generations):
        off = []
        for i in range(pop_size):
            a, b, c = pop[rng.choice(pop_size, 3, replace=False)]
            cross = rng.rand(nk) < 0.9
            cross[rng.randint(nk)] = True
            off.append(np.where(cross, np.clip(a + 0.8 * (b - c), lo, hi), pop[i]))
        combined = np.vstack([pop, off])
        combined_objs = np.vstack([objs, np.array([evaluate(ind) for ind in off])])
        fronts = nds(combined_objs)
        new_p, new_o = [], []
        for front in fronts:
            if len(new_p) + len(front) <= pop_size:
                new_p.extend(front)
                new_o.extend(combined_objs[front].tolist())
            else:
                order = np.argsort(-crowding(combined_objs, front))
                for t in order[:pop_size - len(new_p)]:
                    new_p.append(front[t])
                    new_o.append(combined_objs[front[t]].tolist())
                break
        pop, objs = combined[new_p], np.array(new_o)
    fronts = nds(objs)
    pf = [{k: round(float(pop[i][j]), 6) for j, k in enumerate(keys)} for i in fronts[0]]
    return {"pareto_front": [{"params": p, "rmse": round(objs[i][0], 6),
            "complexity": round(objs[i][1], 6)} for i, p in enumerate(pf)],
            "n_solutions": len(pf)}
