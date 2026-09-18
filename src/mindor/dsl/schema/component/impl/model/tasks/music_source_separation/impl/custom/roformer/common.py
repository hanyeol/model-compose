from pydantic import BaseModel, Field

class CommonRoFormerModelParamsConfig(BaseModel):
    dim: int = Field(..., description="Transformer feature dimension used across time/frequency blocks.")
    depth: int = Field(..., description="Number of stacked time+frequency transformer blocks.")
    stereo: bool = Field(default=True, description="Whether the model consumes stereo (2-channel) mixes; mono when false.")
    num_stems: int = Field(default=1, description="Number of stems the checkpoint separates.")
    time_transformer_depth: int = Field(default=2, description="Depth of each time-axis transformer.")
    freq_transformer_depth: int = Field(default=2, description="Depth of each frequency-axis transformer.")
    heads: int = Field(default=8, description="Number of attention heads per transformer.")
    dim_head: int = Field(default=64, description="Dimension per attention head.")
    stft_n_fft: int = Field(default=2048, description="STFT window size in samples.")
    stft_hop_length: int = Field(default=512, description="STFT hop length in samples.")
    stft_win_length: int = Field(default=2048, description="STFT windowing length in samples.")
    flash_attn: bool = Field(default=True, description="Whether Flash Attention is used inside transformer blocks.")
