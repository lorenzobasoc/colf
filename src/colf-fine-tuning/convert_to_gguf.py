"""
Script per convertire il modello Qwen2.5-1.5B fine-tuned in formato GGUF
Ottimizzato per Raspberry Pi 4 (4GB RAM)

Requisiti:
pip install transformers torch

Poi clonare llama.cpp:
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make
"""

import os
import sys
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

def merge_lora_and_save(
    model_path: str = "./model_v2_final",
    output_path: str = "./model_v2_merged",
):
    """
    Unisce il modello base Qwen con gli adapter LoRA e salva il modello completo
    """
    print(f"🔄 Caricamento modello da {model_path}...")
    
    # Carica il modello con gli adapter LoRA
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="cpu",
        trust_remote_code=True
    )
    
    # Carica il tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True
    )
    
    print(f"✅ Modello caricato. Parametri: {model.num_parameters():,}")
    
    # Salva il modello unito
    print(f"💾 Salvataggio modello unito in {output_path}...")
    os.makedirs(output_path, exist_ok=True)
    
    model.save_pretrained(
        output_path,
        safe_serialization=True  # Usa formato safetensors
    )
    tokenizer.save_pretrained(output_path)
    
    print(f"✅ Modello unito salvato in {output_path}")
    return output_path


def convert_to_gguf(
    model_path: str = "./model_v2_merged",
    llama_cpp_path: str = "../llama.cpp",
    output_name: str = "qwen2.5-1.5b-colf-v2"
):
    """
    Converte il modello in formato GGUF usando llama.cpp
    
    Nota: Richiede llama.cpp clonato localmente
    """
    llama_cpp_path = Path(llama_cpp_path)
    
    if not llama_cpp_path.exists():
        print(f"❌ llama.cpp non trovato in {llama_cpp_path}")
        print("\nEsegui:")
        print("  git clone https://github.com/ggerganov/llama.cpp")
        print("  cd llama.cpp")
        print("  make")
        return None
    
    # Path degli script di conversione
    convert_script = llama_cpp_path / "convert_hf_to_gguf.py"
    quantize_bin = llama_cpp_path / "llama-quantize"
    
    if not convert_script.exists():
        print(f"❌ Script di conversione non trovato: {convert_script}")
        return None
    
    # Output paths
    gguf_fp16 = f"{output_name}-fp16.gguf"
    gguf_q4 = f"{output_name}-q4_k_m.gguf"
    
    print("\n" + "="*60)
    print("📝 CONVERSIONE IN GGUF (FP16)")
    print("="*60)
    
    # Converti in GGUF FP16
    cmd_convert = f"python {convert_script} {model_path} --outfile {gguf_fp16} --outtype f16"
    print(f"Comando: {cmd_convert}\n")
    os.system(cmd_convert)
    
    if not Path(gguf_fp16).exists():
        print(f"❌ Conversione fallita: {gguf_fp16} non creato")
        return None
    
    print(f"✅ Modello FP16 creato: {gguf_fp16}")
    
    # Quantizza a Q4_K_M (ottimale per Raspberry Pi 4)
    if quantize_bin.exists():
        print("\n" + "="*60)
        print("🔧 QUANTIZZAZIONE Q4_K_M (ottimizzato per Raspberry)")
        print("="*60)
        
        cmd_quantize = f"{quantize_bin} {gguf_fp16} {gguf_q4} Q4_K_M"
        print(f"Comando: {cmd_quantize}\n")
        os.system(cmd_quantize)
        
        if Path(gguf_q4).exists():
            print(f"✅ Modello quantizzato creato: {gguf_q4}")
            
            # Mostra dimensioni
            fp16_size = Path(gguf_fp16).stat().st_size / (1024**3)
            q4_size = Path(gguf_q4).stat().st_size / (1024**3)
            
            print(f"\n📊 Confronto dimensioni:")
            print(f"  FP16:  {fp16_size:.2f} GB")
            print(f"  Q4_K_M: {q4_size:.2f} GB (riduzione: {(1-q4_size/fp16_size)*100:.1f}%)")
            
            return gguf_q4
    else:
        print(f"⚠️  llama-quantize non trovato, salto la quantizzazione")
        return gguf_fp16


def main():
    print("="*60)
    print("🚀 CONVERSIONE MODELLO COLF PER RASPBERRY PI")
    print("="*60)
    
    # Step 1: Unisci LoRA con modello base
    merged_path = merge_lora_and_save(
        model_path="./model_v2_final",
        output_path="./model_v2_merged"
    )
    
    # Step 2: Converti in GGUF
    gguf_path = convert_to_gguf(
        model_path=merged_path,
        llama_cpp_path="../llama.cpp",
        output_name="qwen2.5-1.5b-colf-v2"
    )
    
    if gguf_path:
        print("\n" + "="*60)
        print("✅ CONVERSIONE COMPLETATA!")
        print("="*60)
        print(f"\n📦 Modello pronto per Raspberry Pi: {gguf_path}")
        print("\nProssimi passi:")
        print("1. Copia il file .gguf sul Raspberry Pi")
        print("2. Installa: pip install llama-cpp-python")
        print("3. Testa con test_gguf_inference.py")
        print("4. Integra in FastAPI")
    else:
        print("\n❌ Conversione fallita. Verifica i requisiti.")


if __name__ == "__main__":
    main()
