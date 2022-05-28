import os
import sys
import torch

base_dir = os.path.join(os.getcwd(), '..')
sys.path.append(base_dir)

import src.fair as fair
from src.fair.tools import step_I, step_kernel


def compute_means(scenario_dataset):
    base_kwargs = fair.get_params()
    means = dict()
    for name, scenario in scenario_dataset.scenarios.items():
        res = fair.run(scenario.full_timesteps.numpy(),
                       scenario.full_emissions.T.numpy(),
                       base_kwargs)
        S = res['S']
        S = scenario.trim_hist(S)
        means.update({scenario: torch.from_numpy(S).float()})
    return means


def compute_I(scenario_dataset, ks, d, mu, sigma):
    I = [compute_I_scenario(scenario_dataset, scenario, ks, d, mu, sigma)
         for scenario in scenario_dataset.scenarios.values()]
    I = torch.cat(I, dim=-2)
    return I


def compute_I_scenario(scenario_dataset, scenario, ks, d, mu, sigma):
    scenario_emissions_std = (scenario.full_emissions - mu) / sigma
    dataset_emissions_std = (scenario_dataset.full_emissions - mu) / sigma
    Ks = [k(dataset_emissions_std, scenario_emissions_std).evaluate() for k in ks]
    K = torch.stack(Ks, dim=-1)
    I = torch.zeros(K.shape)
    for t in range(1, len(scenario_emissions_std)):
        I_old = I[:, t - 1]
        K_new = K[:, t]
        I_new = step_I(I_old, K_new, d.unsqueeze(0))
        I[:, t] = I_new.squeeze()
    return I


def compute_covariance(scenario_dataset, I, q, d):
    Kj = [compute_covariance_scenario(scenario_dataset, scenario, I, q, d)
          for scenario in scenario_dataset.scenarios.values()]
    Kj = torch.cat(Kj, dim=-2)
    Kj = scenario_dataset.trim_hist(Kj)
    return Kj


def compute_covariance_scenario(scenario_dataset, scenario, I, q, d):
    I_scenario = I[scenario_dataset.full_slices[scenario.name]]
    Kj = torch.zeros_like(I_scenario)
    for t in range(1, I_scenario.size(0)):
        Kj_old = Kj[t - 1]
        I_new = I_scenario[t]
        Kj_new = step_kernel(Kj_old, I_new, q.unsqueeze(0), d.unsqueeze(0))
        Kj[t] = Kj_new
    Kj = scenario.trim_hist(Kj)
    return Kj.permute(1, 0, 2)
