from typing import Optional, List, Union
from pydantic import Field
from ...common import CommonModelTrainerActionConfig

class TextClassificationModelTrainerActionConfig(CommonModelTrainerActionConfig):
    # Data formatting
    text_column: str = Field(default="text", description="Dataset column that holds the input text.")
    label_column: str = Field(default="label", description="Dataset column that holds the class label.")

    # Label mapping
    num_labels: Optional[int] = Field(default=None, description="Number of output classes; auto-inferred from `label_column` when unset.")
    label_names: Optional[Union[List[str], str]] = Field(default=None, description="Ordered class-name list used to build `id2label` / `label2id`.")

    # Training strategy
    max_seq_length: Optional[int] = Field(default=None, description="Maximum tokenized sequence length used during training.")
