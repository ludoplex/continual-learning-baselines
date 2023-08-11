#!/usr/bin/env python3
import numpy as np
import torch
import torchvision.transforms as transforms
from torch.optim import SGD
from torchvision.transforms import ToTensor

from avalanche.benchmarks.classic import SplitCIFAR100
from avalanche.evaluation.metrics import accuracy_metrics, loss_metrics
from avalanche.logging import InteractiveLogger
from avalanche.training.plugins import EvaluationPlugin
from avalanche.training.supervised import ER_AML
from experiments.utils import create_default_args, set_seed
from models import SingleHeadReducedResNet18


def eraml_scifar100(override_args=None):
    """
    Reproducing ER-AML experiments from paper
    "New insights on Reducing Abrupt Representation Change in Online Continual Learning"
    by Lucas Caccia et. al
    https://openreview.net/forum?id=N8MaByOzUfb
    """
    args = create_default_args(
        {
            "cuda": 0,
            "mem_size": 10000,
            "lr": 0.1,
            "temp": 0.1,
            "train_mb_size": 10,
            "seed": None,
            "batch_size_mem": 10,
        },
        override_args,
    )
    set_seed(args.seed)
    fixed_class_order = np.arange(100)
    device = torch.device(
        f"cuda:{args.cuda}" if torch.cuda.is_available() and args.cuda >= 0 else "cpu"
    )
    unique_transform = transforms.Compose(
        [
            ToTensor(),
            transforms.Normalize((0.5071, 0.4866, 0.4409), (0.2009, 0.1984, 0.2023)),
        ]
    )
    scenario = SplitCIFAR100(
        20,
        return_task_id=False,
        seed=0,
        fixed_class_order=fixed_class_order,
        shuffle=True,
        class_ids_from_zero_in_each_exp=False,
        train_transform=unique_transform,
        eval_transform=unique_transform,
    )
    input_size = (3, 32, 32)
    model = SingleHeadReducedResNet18(100)
    optimizer = SGD(model.parameters(), lr=args.lr)
    interactive_logger = InteractiveLogger()
    loggers = [interactive_logger]
    training_metrics = []
    evaluation_metrics = [
        accuracy_metrics(epoch=True, stream=True),
        loss_metrics(epoch=True, stream=True),
    ]
    evaluator = EvaluationPlugin(
        *training_metrics,
        *evaluation_metrics,
        loggers=loggers,
    )
    plugins = []
    cl_strategy = ER_AML(
        model=model,
        feature_extractor=model.feature_extractor,
        optimizer=optimizer,
        plugins=plugins,
        evaluator=evaluator,
        device=device,
        train_mb_size=args.train_mb_size,
        eval_mb_size=64,
        mem_size=args.mem_size,
        batch_size_mem=args.batch_size_mem,
    )
    for t, experience in enumerate(scenario.train_stream):
        cl_strategy.train(
            experience,
            num_workers=0,
            drop_last=True,
        )
        cl_strategy.eval(scenario.test_stream[: t + 1])
    return cl_strategy.eval(scenario.test_stream)


if __name__ == "__main__":
    res = eraml_scifar100()
    print(res)
