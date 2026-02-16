from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer, 
    TrainingArguments, 
    Trainer,
    TrainerCallback
)
from peft import LoraConfig, get_peft_model, PeftModel
import torch
from datetime import datetime

# Configurazione
model_name = 'Qwen/Qwen2.5-1.5B-Instruct'
checkpoint_path = './model/checkpoint-504' # Ultimo checkpoint salvato
dataset_path = 'train_data_focused.jsonl' # Dataset focalizzato su categorie specifiche
model_version = 'v2'  # Versione del modello per salvataggio

print("="*70)
print("🔄 CONTINUAL LEARNING - Training incrementale")
print("="*70)

# Callback per logging
class LoggingCallback(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs:
            current_time = datetime.now().strftime("%H:%M:%S")
            step = state.global_step
            epoch = state.epoch
            
            log_msg = f"[{current_time}] Step {step} | Epoch {epoch:.2f}"
            
            if 'loss' in logs:
                log_msg += f" | Loss: {logs['loss']:.4f}"
            if 'learning_rate' in logs:
                log_msg += f" | LR: {logs['learning_rate']:.2e}"
                
            print(log_msg)
    
    def on_epoch_end(self, args, state, control, **kwargs):
        print(f"\n{'='*70}")
        print(f"✓ Epoca {int(state.epoch)} completata!")
        print(f"{'='*70}\n")

print(f"\n[1/5] 📦 Caricamento checkpoint: {checkpoint_path}")

# Carica tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token

# Carica modello base
base_model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float32,
    device_map="auto",
    low_cpu_mem_usage=True
)

# Carica adattatori esistenti
model = PeftModel.from_pretrained(base_model, checkpoint_path)
print("✓ Checkpoint caricato")

# Unisci adattatori al modello base
model = model.merge_and_unload()

# Riconfigura LoRA
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    bias="none",
    task_type="CAUSAL_LM"
)

model = get_peft_model(model, lora_config)
trainable_params, all_params = model.get_nb_trainable_parameters()
print(f"✓ LoRA riconfigurato")
print(f"  - Parametri trainabili: {trainable_params:,}")
print(f"  - Percentuale: {100 * trainable_params / all_params:.2f}%")

# Carica dataset
print(f"\n[2/5] 📂 Caricamento dataset: {dataset_path}")
dataset = load_dataset('json', data_files=dataset_path)['train']
print(f"✓ Dataset caricato: {len(dataset)} esempi")

# Mostra distribuzione categorie
from collections import Counter
categories = [item['response'] for item in dataset]
cat_counts = Counter(categories)

print("\n📊 Top 10 categorie per numero di esempi:")
for cat, count in cat_counts.most_common(10):
    print(f"  {cat:20s} {count:3d} esempi")

# Tokenizzazione
print("\n[3/5] 🔤 Tokenizzazione del dataset...")

def tokenize(batch):
    # Aggiungi il template completo
    full_texts = [f"{inst}\n{resp}" for inst, resp in zip(batch['instruction'], batch['response'])]
    
    tokens = tokenizer(
        full_texts, 
        truncation=True, 
        padding='max_length', 
        max_length=256,
    )
    
    tokens['labels'] = tokens['input_ids'].copy()
    
    return tokens

tokenized_data = dataset.map(
    tokenize,
    batched=True,
    remove_columns=dataset.column_names
)
print("✓ Tokenizzazione completata")

# Training
print("\n[4/5] 🎯 Configurazione training...")

training_args = TrainingArguments(
    output_dir='./model_' + model_version,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=1e-4,  # PIÙ BASSO del training iniziale
    num_train_epochs=15,
    fp16=False,
    logging_steps=10,
    save_strategy='epoch',
    save_total_limit=3,
    report_to='none',
    remove_unused_columns=False,
    warmup_steps=10,
    weight_decay=0.01,  # Previene overfitting
)

print(f"  - Learning rate: {training_args.learning_rate:.0e} (ridotto)")
print(f"  - Epoche: {training_args.num_train_epochs}")
print(f"  - Batch effettivo: {training_args.per_device_train_batch_size * training_args.gradient_accumulation_steps}")
print(f"  - Weight decay: {training_args.weight_decay}")

trainer = Trainer(
    model=model,
    train_dataset=tokenized_data,
    args=training_args,
    tokenizer=tokenizer,
    callbacks=[LoggingCallback()]
)

print("\n[5/5] ⏳ Avvio training incrementale...")
print("="*70 + "\n")

start_time = datetime.now()
trainer.train()
end_time = datetime.now()

training_time = (end_time - start_time).total_seconds()
print(f"\n✓ Training completato in {training_time/60:.1f} minuti")

# Salvataggio
print(f"\n💾 Salvataggio modello {model_version}...")
model.save_pretrained('./model_' + model_version)
tokenizer.save_pretrained('./model_' + model_version)
print("✓ Modello salvato in './model_" + model_version + "'")

print("\n" + "="*70)
print("✅ CONTINUAL LEARNING COMPLETATO!")
print("="*70)