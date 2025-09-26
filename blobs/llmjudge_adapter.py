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
import re
import json

# plain copy
from dotenv import load_dotenv
from azure.ai.inference.aio import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage, JsonSchemaFormat
from pydantic import BaseModel

# Initialize a logger for this module
logger = configure_logger(__name__)

class ResponseFormat(BaseModel, extra="forbid"):
    score: int
    explanation: str

class LLMJudgeAdapter(MetricPort):

    ERROR_INIT_MSG = (
        "[LLMJudgeAdapter] There was an error initializing the LLMJudgeAdapter: {}"
    )
    ERROR_RETRIEVING_CONNECTORS_MSG = (
        "[LLMJudgeAdapter] There was an error retrieving metric connectors: {}"
    )
    ERROR_EVALUATING_RESULT_MSG = (
        "[LLMJudgeAdapter] There was an error evaluating the individual result: {}"
    )
    ERROR_RETRIEVING_RESULTS_MSG = (
        "[LLMJudgeAdapter] There was an error retrieving results: {}"
    )
    NO_CONNECTOR_AVAILABLE_MSG = (
        "[LLMJudgeAdapter] No metric connector available for evaluation."
    )
    FAILED_MODEL_PREDICTIONS_MSG = (
        "[LLMJudgeAdapter] Failed to get model predictions from the evaluation model."
    )
    LOADING_CONNECTOR_MSG = "[LLMJudgeAdapter] Loading connector with model '{model}' and adapter '{adapter}'"
    SUCCESSFULLY_LOADED_CONNECTORS_MSG = (
        "[LLMJudgeAdapter] Successfully loaded all metric connectors."
    )

    def __init__(self):
        """
        Initialize the LLMJudgeAdapter with metric configuration and connector.
        """
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

            self.model_clients = [
                ChatCompletionsClient(
                    endpoint = self.API_ENDPOINT,
                    credential=AzureKeyCredential(self.API_KEY),
                    model="grok-3-mini-moonshot"
                ),
                ChatCompletionsClient(
                    endpoint = self.API_ENDPOINT,
                    credential=AzureKeyCredential(self.API_KEY),
                    model="phi-4-mini-moonshot"
                ),
                ChatCompletionsClient(
                    endpoint = self.API_ENDPOINT,
                    credential=AzureKeyCredential(self.API_KEY),
                    model="deepseek-41-moonshot"
                )
            ]
            self.prompt = """
            <ENTER PROMPT HERE>
            """
            self.system_prompt = "<ENTER SYSTEM PROMPT HERE>"

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

    async def _get_message_payload(self, generated_response: str, target_response: str):
        messages = [
            SystemMessage(content=self.system_prompt),
            UserMessage(content=self.prompt.format(text=generated_response, target=target_response))
        ]
        return messages
    
    async def _get_llm_score_and_explanation(self, llm_response: str) -> dict:
        think_match_exist = re.match(r"<think>(.*?)</think>(.*?)", llm_response, re.DOTALL)
        if think_match_exist:
            output = re.search(r'\{[^}]*\}', think_match_exist.group(2)).group()
            output = json.loads(output)
        else:
            output = json.loads(llm_response)
        return output["score"], output["explanation"]
    
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
            scores, model_evals = [], []
            for client in self.model_clients:
                msg_template = await self._get_message_payload(entity.predicted_result.response, entity.target)
                response = await client.complete(
                    response_format="json_object",
                    messages= msg_template,
                    temperature=1,
                    top_p=1,
                    max_tokens=4028 
                )
                score, model_eval = await self._get_llm_score_and_explanation(response.choices[0].message.content)
                scores.append(score)
                model_evals.append({response.model: model_eval})
            
            avg_score = 0
            if scores:
                avg_score = round(sum(scores) / len(scores), 2)

            return {
                "prompt": entity.prompt,
                "predicted_value": entity.predicted_result.response,
                "target": entity.target,
                "llm_score": avg_score,
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
            llm_scores = []
            for entity in entities:
                llm_score = entity.evaluated_result.get("llm_score")
                llm_scores.append(llm_score)

            if not llm_scores:
                return {"llmjudge": {"f1": 0.0}}    
            return {
                "llmjudge": {
                    "average_score": sum(llm_scores) / len(llm_scores),
                },
            }
        except Exception as e:
            logger.error(self.ERROR_RETRIEVING_RESULTS_MSG.format(e))
            raise

    def install_requirements(self) -> None:
        """
        Installs the required packages for the custom metric.

        This function will iterate over the list of packages in the `requirements`
        variable and install each one using pip.

        Raises:
            subprocess.CalledProcessError: If the installation of any package fails.
        """
        # TODO 6 (Optional): If your custom metric has dependencies, add them into the list below. We will attempt
        # to install and import the packages. In this example, our dependency is the library 'httpx'.
        dependencies = ["httpx"]
        for dependency in dependencies:
            try:
            # Check if the package is already installed
                __import__(dependency)
                logger.info(f"{dependency} is already installed.")                
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", dependency]
                )
                logger.info(f"Successfully installed {dependency}")
                # Dynamically import the package after successful installation
                globals()[dependency] = importlib.import_module(dependency)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {dependency}: {e}")
                raise