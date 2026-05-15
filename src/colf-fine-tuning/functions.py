import torch
from transformers import (AutoTokenizer, BitsAndBytesConfig, AutoModelForCausalLM)
from huggingface_hub import login
from datasets import Dataset, load_dataset
from peft import LoraConfig, PeftModel
import warnings
from datasets import load_dataset
import torch

warnings.filterwarnings("ignore")

# Logs
def _log_model_specs(model):
    print(f"Model: {model.name_or_path}")
    print(f"Device: {model.device}")
    print(f"DType: {model.dtype}")

    if hasattr(model, "is_quantized") and model.is_quantized:
        print("Quantization: Enabled")
        print(f"  - 4bit: {model.is_loaded_in_4bit}")
        print(f"  - Quant Type: {model.hf_quantizer.quantization_config.bnb_4bit_quant_type}")
        print(f"  - Compute DType: {model.hf_quantizer.quantization_config.bnb_4bit_compute_dtype}")
    else:
        print("Quantization: Disabled")

def _log_test_result(idx, instruction, expected, actual):
    print(f"\n{'='*60}")
    print(f"📝 Esempio {idx + 1}")
    print(f"{'='*60}")
    print(f"Domanda:\n   {instruction}")
    print(f"\n✅ Risposta attesa:\n   {expected}")
    print(f"\n🤖 Risposta Modello:\n   {actual}")


def _define_device():
    # Prefer MPS (Metal Performance Shaders) on Apple Silicon Macs
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        print("using MPS device on macOS")
        return torch.device("mps")

    # Fall back to CUDA (NVIDIA GPU) or CPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"using {device}")
    return device

device = _define_device()

def load_model(model_name, use_fine_tuned_model, adapter_path):
    compute_dtype = torch.bfloat16

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    print(f"✓ Tokenizer caricato: {model_name}")

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,  # computation precision for the forward pass
        bnb_4bit_use_double_quant=True,  # quantize the quantization constants (saves ~0.4 bit/param)
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype= compute_dtype, 
        attn_implementation="eager",  # disables Flash Attention for broader compatibility
        quantization_config=quantization_config,
        device_map="auto",  # automatically place layers across available devices
    )
    print(f"✓ Modello base caricato")

    if (use_fine_tuned_model):
        tuned_model = PeftModel.from_pretrained(model, adapter_path)
        tuned_model = tuned_model.merge_and_unload().eval()
        
        print(f"✓ Modello fine tuned caricato")
        _log_model_specs(tuned_model)

        return (tuned_model, tokenizer)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    _log_model_specs(model)

    return (model, tokenizer)

def generate(model, instruction, tokenizer):
    prompt = f'{instruction}\n ### \n'

    messages = [
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True).to(device)

    with torch.no_grad():
        out = model.generate(
            **inputs, 
            max_new_tokens=50,
            pad_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(out[0], skip_special_tokens=True)
    # response = response.split("\n ### \n")[-1].strip()
    return response