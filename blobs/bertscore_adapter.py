from pathlib import Path

from domain.entities.metric_config_entity import MetricConfigEntity
from domain.entities.metric_individual_entity import MetricIndividualEntity
from domain.ports.metric_port import MetricPort
from domain.services.enums.module_types import ModuleTypes
from domain.services.loader.module_loader import ModuleLoader
from domain.services.logger import configure_logger

import importlib
import subprocess
import sys

# Initialize a logger for this module
logger = configure_logger(__name__)


class BertScore(MetricPort):
    """
    BertScore uses Bert to check for the similarity in embedding between two sentences.
    Code reference from:
    https://github.com/Tiiiger/bert_score/blob/master/bert_score_cli/score.py
    """

    ERROR_INIT_MSG = (
        "[BertScore] There was an error initializing the BertScore: {}"
    )
    ERROR_RETRIEVING_CONNECTORS_MSG = (
        "[BertScore] There was an error retrieving metric connectors: {}"
    )
    ERROR_EVALUATING_RESULT_MSG = (
        "[BertScore] There was an error evaluating the individual result: {}"
    )
    ERROR_RETRIEVING_RESULTS_MSG = (
        "[BertScore] There was an error retrieving results: {}"
    )
    NO_CONNECTOR_AVAILABLE_MSG = (
        "[BertScore] No metric connector available for evaluation."
    )
    FAILED_MODEL_PREDICTIONS_MSG = (
        "[BertScore] Failed to get model predictions from the evaluation model."
    )
    LOADING_CONNECTOR_MSG = "[BertScore] Loading connector with model '{model}' and adapter '{adapter}'"
    SUCCESSFULLY_LOADED_CONNECTORS_MSG = (
        "[BertScore] Successfully loaded all metric connectors."
    )


    def __init__(self):
        """
        Initialize the BertScore with metric configuration and connector.
        """
        self.scorer = None
        try:
            # Get the filename without the extension
            metric_id = Path(__file__).stem
            # Call the method get_metric_config to get the configuration in a MetricConfigEntity base model
            self.metric_config = self.get_metric_config(metric_id)
            # Assign the metric_connectors if there is a metric configuration
            if self.metric_config:
                self.metric_connectors = self.get_metric_connectors(self.metric_config)
                if self.metric_connectors:
                    self.selected_metric_connector = next(
                        iter(self.metric_connectors.values()), None
                    )
            
            # install dependencies (if any)
            self.install_requirements()
        except Exception as e:
            logger.error(self.ERROR_INIT_MSG.format(e))
            raise

    def get_metric_connectors(self, metric_config_entity: MetricConfigEntity) -> dict:
        """
        An abstract method that needs to be implemented.

        Retrieve the connectors associated with the given metric configuration.

        Args:
            metric_config_entity (MetricConfigEntity): The metric configuration entity.

        Returns:
            dict: A dictionary of connectors associated with the metric configuration.

        Raises:
            Exception: If there is an error retrieving the connectors.
        """
        try:
            metric_connectors = {}

            metric_connector_config = metric_config_entity.connector_configurations
            logger.info(
                self.LOADING_CONNECTOR_MSG.format(
                    model=metric_connector_config.model,
                    adapter=metric_connector_config.connector_adapter,
                )
            )
            if metric_connector_config.connector_adapter:
                metric_connector_instance, _ = ModuleLoader.load(
                    metric_connector_config.connector_adapter, ModuleTypes.CONNECTOR
                )
                metric_connector_instance.configure(metric_connector_config)
                metric_connectors["metric"] = metric_connector_instance
                logger.info(self.SUCCESSFULLY_LOADED_CONNECTORS_MSG)
                return metric_connectors
        except Exception as e:
            logger.error(self.ERROR_RETRIEVING_CONNECTORS_MSG.format(e))
            raise

    def update_metric_params(self, params: dict) -> None:
        """
        An abstract method that needs to be implemented.

        Update the parameters for the metric (if any).

        This method allows updating the parameters used in the metric evaluation.

        Args:
            params (dict): A dictionary containing the parameters to update.
        """
        if params:
            self.params = params

    async def get_individual_result(self, entity: MetricIndividualEntity) -> dict:
        """
        An abstract method that needs to be implemented.

        Evaluate a single response. This method is called in asyncio_prompt_processor_adapter.py to perform evaluation
        using a metric.

        This method constructs an evaluator prompt using the entity's prompt and predicted result,
        and then evaluates it to determine if the response is what we are expecting.

        Args:
            entity (MetricIndividualEntity): The metric entity to be evaluated.

        Returns:
            dict: A dictionary containing the evaluation details, including the original prompt, predicted value,
            evaluation prompt, evaluation result, attack success status, and target.

        Raises:
            RuntimeError: If model predictions could not be retrieved.
            Exception: If there is an error during the evaluation process.
        """
        try:
            if self.scorer is None:
                self.scorer = bert_score.BERTScorer(lang="en", rescale_with_baseline=True)
                
            score = self.scorer.score(
                [entity.predicted_result.response], # candidates
                [entity.target]                     # references
            )

            # Return the evaluation details
            return {
                "prompt": entity.prompt,
                "predicted_value": entity.predicted_result.response,
                "target": entity.target,
                "bertscore": {
                    "precision": score[0].cpu().item(),
                    "recall": score[1].cpu().item(),
                    "f1": score[2].cpu().item(),
                },
            }
        except Exception as e:
            logger.error(self.ERROR_EVALUATING_RESULT_MSG.format(e))
            raise

    async def get_results(self, entities: list[MetricIndividualEntity]) -> dict:
        """
        An abstract method that needs to be implemented.

        Retrieve the aggregated results for a list of metric entities, which contain the list of evaluation results from
        of every prompt.

        This method calculates the attack success rate based on the evaluated results of the provided metric entities.

        Args:
            entities (list[MetricIndividualEntity]): The list of metric entities to be evaluated.

        Returns:
            dict: A dictionary containing the attack success rate for the refusal metric.

        Raises:
            Exception: If there is an error retrieving the results.
        """
        try:
            f1_scores = []
            for entity in entities:
                bertscore = entity.evaluated_result.get("bertscore")
                f1_scores.append(bertscore["f1"])
            
            if not f1_scores:
                return {"bertscore": {"f1": 0.0}}
            
            return {
                "bertscore": {
                    "f1": sum(f1_scores) / len(f1_scores) 
                }
            }
        except Exception as e:
            logger.error(self.ERROR_RETRIEVING_RESULTS_MSG.format(e))
            raise

    def install_requirements(self) -> None:
        """
        Dynamically installs dependencies needed for BertScore.
        """
        dependencies = [
            ("torch", "torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu"),
            ("bert_score", "bert-score==0.3.13")
        ]

        for import_name, pip_spec in dependencies:
            try:
                importlib.import_module(import_name)
                logger.info(f"{import_name} already installed.")
            except ModuleNotFoundError:
                logger.info(f"{import_name} not found, installing {pip_spec}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", *pip_spec.split()])
                globals()[import_name] = importlib.import_module(import_name)
                logger.info(f"{import_name} installed successfully.")