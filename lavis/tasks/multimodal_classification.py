import json
import os

import numpy as np
import torch

from lavis.common.utils import main_process, save_result
from lavis.common.registry import registry

from lavis.tasks.base_task import BaseTask


@registry.register_task("multimodal_classification")
class MultimodalClassificationTask(BaseTask):
    ID_KEY = "image_id"

    def __init__(self):
        super().__init__()

    def build_datasets(self, cfg):
        datasets = super().build_datasets(cfg)

        assert "test" in datasets, "No testing split is present."
        return datasets

    def valid_step(self, model, samples):
        results = []

        outputs = model.predict(samples)

        predictions = outputs["predictions"]
        targets = outputs["targets"]

        predictions = predictions.max(1)[1].cpu().numpy()
        targets = targets.cpu().numpy()

        indices = samples[self.ID_KEY]

        for pred, tgt, index in zip(predictions, targets, indices):
            if isinstance(index, torch.Tensor):
                index = index.item()

            results.append(
                {self.ID_KEY: index, "prediction": pred.item(), "target": tgt.item()}
            )

        return results

    def after_evaluation(self, val_result, split_name, epoch, **kwargs):
        eval_result_file = save_result(
            result=val_result,
            result_dir=registry.get_path("result_dir"),
            filename="{}_epoch{}".format(split_name, epoch),
            remove_duplicate=self.ID_KEY,
        )

        metrics = self._report_metrics(
            eval_result_file=eval_result_file, split_name=split_name
        )

        return metrics

    @main_process
    def _report_metrics(self, eval_result_file, split_name):
        results = json.load(open(eval_result_file))

        predictions = np.array([res["prediction"] for res in results])
        targets = np.array([res["target"] for res in results])

        accuracy = (targets == predictions).sum() / targets.shape[0]
        metrics = {"agg_metrics": accuracy, "acc": accuracy}

        log_stats = {split_name: {k: v for k, v in metrics.items()}}

        with open(
            os.path.join(registry.get_path("output_dir"), "evaluate.txt"), "a"
        ) as f:
            f.write(json.dumps(log_stats) + "\n")

        return metrics