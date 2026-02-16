import os
import math
import torch
from torch.utils.data import DataLoader
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, default_data_collator
from peft import PeftModel

print("="*60)
print("🧪 VALUTAZIONE MODELLO BASE VS FINE-TUNED")
print("="*60)

# Configurazione
model_name = 'Qwen/Qwen2.5-1.5B-Instruct'
adapter_path = './model/checkpoint-504'  # ← CAMBIA CON IL TUO CHECKPOINT
dataset_path = 'train_data.jsonl'

# Rileva dispositivo (MPS per Apple Silicon, altrimenti CPU)
if torch.backends.mps.is_available():
    device = 'mps'  # Apple Silicon M1/M2/M3
    print("✅ Dispositivo: Apple Silicon (MPS)")
elif torch.cuda.is_available():
    device = 'cuda'
    print("✅ Dispositivo: NVIDIA GPU")
else:
    device = 'cpu'
    print("✅ Dispositivo: CPU")

# 1. Carica tokenizer
print("\n[1/4] 📦 Caricamento tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
print("✅ Tokenizer caricato")

# 2. Carica modello base
print("\n[2/4] 🤖 Caricamento modello base...")
base_model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float32,  # CPU/MPS compatibile
    device_map='auto',
    trust_remote_code=True,
    low_cpu_mem_usage=True
).eval()
print(f"✅ Modello base caricato su {device}")

# 3. Carica modello fine-tuned
print("\n[3/4] 🎯 Caricamento modello fine-tuned...")
print(f"   Adapter path: {adapter_path}")

tmp_model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float32,
    device_map='auto',
    trust_remote_code=True,
    low_cpu_mem_usage=True
)

tuned_model = PeftModel.from_pretrained(tmp_model, adapter_path)
tuned_model = tuned_model.merge_and_unload().eval()
print("✅ Modello fine-tuned caricato")

# 4. Prepara dataset
print("\n[4/4] 📂 Preparazione dataset di valutazione...")

def tokenize(batch):
    texts = [
        f"### Instructions:\n{inst}\n### Response:\n{out}"
        for inst, out in zip(batch['instruction'], batch['response'])
    ]

    tokens = tokenizer(
        texts,
        padding='max_length',
        truncation=True,
        max_length=256,
        return_tensors='pt'
    )

    tokens['labels'] = tokens['input_ids'].clone()
    return tokens

eval_ds = load_dataset('json', data_files=dataset_path)['train']
print(f"   Dataset: {len(eval_ds)} esempi")

eval_ds = eval_ds.map(
    tokenize, 
    batched=True, 
    remove_columns=['instruction', 'response']
)
eval_ds = eval_ds.with_format('torch')

eval_loader = DataLoader(
    eval_ds,
    batch_size=4,  # Ridotto per Mac
    collate_fn=default_data_collator
)
print(f"✅ Dataset preparato ({len(eval_loader)} batch)")

# # 5. Calcola perplexity
# print("\n" + "="*60)
# print("📊 CALCOLO PERPLEXITY")
# print("="*60)

# @torch.no_grad()
# def compute_perplexity(model, model_name_str):
#     losses = []
    
#     print(f"\n⏳ Calcolo perplexity per {model_name_str}...")
    
#     for i, batch in enumerate(eval_loader):
#         # Sposta batch sul dispositivo corretto
#         batch = {k: v.to(device) for k, v in batch.items()}
        
#         loss = model(**batch).loss
#         losses.append(loss.item())
        
#         # Progress indicator
#         if (i + 1) % 5 == 0 or (i + 1) == len(eval_loader):
#             print(f"   Batch {i+1}/{len(eval_loader)} | Loss media: {sum(losses)/len(losses):.4f}")
    
#     perplexity = math.exp(sum(losses) / len(losses))
#     return perplexity

# base_perplexity = compute_perplexity(base_model, "Modello Base")
# tuned_perplexity = compute_perplexity(tuned_model, "Modello Fine-Tuned")

# print("\n" + "="*60)
# print("📈 RISULTATI PERPLEXITY")
# print("="*60)
# print(f"Modello Base:       {base_perplexity:.2f}")
# print(f"Modello Fine-Tuned: {tuned_perplexity:.2f}")
# print(f"Miglioramento:      {((base_perplexity - tuned_perplexity) / base_perplexity * 100):.1f}%")
# print("="*60)

# # 6. Test generazione
# print("\n" + "="*60)
# print("💬 TEST GENERAZIONE")
# print("="*60)

# raw_data = load_dataset('json', data_files=dataset_path)['train']

def generate(model, instruction):
    prompt = f'### Instructions:\n{instruction}\n### Response:\n'
    token_ids = tokenizer(prompt, return_tensors='pt').input_ids.to(device)

    with torch.no_grad():
        out = model.generate(
            token_ids, 
            max_new_tokens=50,
            temperature=0.1,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id
        )

    full_response = tokenizer.decode(out[0], skip_special_tokens=True)
    # Estrae solo la parte dopo "### Response:"
    response = full_response.split("### Response:\n")[-1].strip()
    return response

# # Test su 5 esempi casuali
# import random
# test_indices = random.sample(range(len(raw_data)), min(5, len(raw_data)))

# for idx in test_indices:
#     instruction = raw_data['instruction'][idx]
#     expected = raw_data['response'][idx]
    
#     print(f"\n{'='*60}")
#     print(f"📝 Esempio {idx + 1}")
#     print(f"{'='*60}")
#     print(f"❓ Domanda:\n   {instruction}")
#     print(f"\n✅ Risposta attesa:\n   {expected}")
#     print(f"\n🤖 Modello Base:\n   {generate(base_model, instruction)}")
#     print(f"\n🎯 Modello Fine-Tuned:\n   {generate(tuned_model, instruction)}")

# print("\n" + "="*60)
# print("✅ VALUTAZIONE COMPLETATA!")
# print("="*60)

# 7. Test interattivo (opzionale)
print("\n💡 Vuoi testare con altre domande? (y/n)")
if input().lower() == 'y':
    print("\n💬 Modalità interattiva (scrivi 'quit' per uscire)")
    while True:
        question = input("\n Classifica questa spesa in una delle seguenti categorie: Cibo/Spesa, Trasporti, Casa, Sanità, Vestiti, Abbonamenti, Bar, Cibo fuori, Viaggi, Festa/Eventi, Sport, Regali, Altro extra, Lavoro, Auto, Intrattenimento .\n\nSpesa: ")
        if question.lower() in ['quit', 'exit', 'q']:
            break
        
        print(f"\n🤖 Base:        {generate(base_model, question)}")
        print(f"🎯 Fine-Tuned:  {generate(tuned_model, question)}")
