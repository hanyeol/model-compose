"""Unit tests for the ``typed-decision`` model-trainer registry wiring.

Importing each family's driver module must side-effect-register it in
``ModelTrainerTaskDriverRegistry`` via its ``@register_model_trainer_task_driver``
decorator.  The runtime ``ModelTrainerComponent`` relies on lazy module import
to populate this registry at ``_create_driver`` time; this test verifies the
convention still holds without exercising the full component lifecycle.
"""

import importlib

from mindor.core.component.services.model_trainer.base import ModelTrainerTaskDriverRegistry
from mindor.dsl.schema.component import ModelTrainerTaskType, ModelTrainerDriverType


class TestTypedDecisionDriverRegistration:
    def _import_family(self, family: str):
        importlib.import_module(
            f"mindor.core.component.services.model_trainer.tasks.typed_decision.{family}"
        )

    def test_all_four_families_register(self):
        for family in ("clef", "laya", "nimble", "kev"):
            self._import_family(family)

        registered = {
            driver.value
            for driver in ModelTrainerTaskDriverRegistry.get(ModelTrainerTaskType.TYPED_DECISION, {}).keys()
        }
        assert {"clef", "laya", "nimble", "kev"} <= registered

    def test_driver_class_matches_component_config_family(self):
        self._import_family("clef")

        driver_class = ModelTrainerTaskDriverRegistry[ModelTrainerTaskType.TYPED_DECISION][ModelTrainerDriverType.CLEF]
        # The driver class carries a `config` class attribute pinning the
        # component-config shape it consumes; this is the handshake the runtime
        # relies on when the registry picks a class by task+driver pair.
        assert driver_class.__name__ == "ClefTypedDecisionModelTrainerTaskDriver"
