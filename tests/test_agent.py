"""Tests for the minimal agent foundation."""
import unittest
from unittest.mock import patch

from agent import agent as agent_module


class AgentTests(unittest.TestCase):
    def test_get_agent_model_forwards_configuration(self) -> None:
        expected_model = object()

        with patch(
            "agent.agent.init_gemini_chat_model", return_value=expected_model
        ) as initialize_model:
            model = agent_module.get_agent_model(
                api_key="test-key", model_name="test-model"
            )

        self.assertIs(model, expected_model)
        initialize_model.assert_called_once_with(
            api_key="test-key", model_name="test-model"
        )


if __name__ == "__main__":
    unittest.main()
