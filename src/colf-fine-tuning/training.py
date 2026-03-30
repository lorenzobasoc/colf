from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer, 
    TrainingArguments, 
    Trainer,
    TrainerCallback
)
from peft import LoraConfig, get_peft_model
import torch
from datetime import datetime

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
        print(f"\n{'='*60}")
        print(f"✓ Epoca {int(state.epoch)} completata!")
        print(f"{'='*60}\n")

model_name = 'Qwen/Qwen2.5-1.5B-Instruct' #Qwen/Qwen3.5-2B
dataset_path = 'train_data.jsonl'

def train(model_name, dataset_path, output_dir):
    print("="*60)
    print("🚀 INIZIO FINE-TUNING")
    print("="*60)

    # 1. Caricamento modello
    print("\n[1/6] 📦 Caricamento modello e tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token
    print(f"✓ Tokenizer caricato: {model_name}")

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        load_in_8bit=False,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )
    print(f"✓ Modello caricato")
    print(f"  - Device: {'GPU' if torch.cuda.is_available() else 'CPU'}")
    print(f"  - Dtype: {model.dtype}")

    # 2. Configurazione LoRA
    print("\n[2/6] ⚙️  Configurazione LoRA...")
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM"
    )

    model = get_peft_model(model, lora_config)
    trainable_params, all_params = model.get_nb_trainable_parameters()
    print(f"✓ LoRA configurato")
    print(f"  - Parametri trainabili: {trainable_params:,} ({100 * trainable_params / all_params:.2f}%)")
    print(f"  - Parametri totali: {all_params:,}")

    # 3. Caricamento dataset
    print("\n[3/6] 📂 Caricamento dataset...")
    dataset = load_dataset('json', data_files=dataset_path)['train']
    print(f"✓ Dataset caricato: {len(dataset)} esempi")

    # 4. Tokenizzazione
    print("\n[4/6] 🔤 Tokenizzazione del dataset...")

    def tokenize(batch):
        texts = [
            f"### Instructions:\n{instruction}\n### Response:\n{response}" 
            for instruction, response in zip(batch['instruction'], batch['response'])
        ]
        
        tokens = tokenizer(
            texts, 
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
    print(f"✓ Tokenizzazione completata")
    print(f"  - Shape: {tokenized_data.shape}")

    # 5. Training
    print("\n[5/6] 🎯 Avvio training...")
    print(f"  - Batch size: 2")
    print(f"  - Gradient accumulation: 8 (batch effettivo: 16)")
    print(f"  - Learning rate: 2e-4")
    print(f"  - Epoche: 50")
    print(f"  - Steps totali: {len(tokenized_data) * 50 // (2 * 8)}")

    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        num_train_epochs=50,
        fp16=False,
        logging_steps=10,
        save_strategy='epoch',
        save_total_limit=3,
        report_to='none',
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        train_dataset=tokenized_data,
        args=training_args,
        tokenizer=tokenizer,
        callbacks=[LoggingCallback()]
    )

    print("\n" + "="*60)
    print("⏳ TRAINING IN CORSO...")
    print("="*60 + "\n")

    start_time = datetime.now()
    trainer.train()
    end_time = datetime.now()

    training_time = (end_time - start_time).total_seconds()
    print(f"\n✓ Training completato in {training_time/60:.1f} minuti")

    # 6. Salvataggio
    print("\n[6/6] 💾 Salvataggio modello...")
    model.save_pretrained(f'{output_dir}/model_adapter')
    tokenizer.save_pretrained(f'{output_dir}/model_adapter')
    print(f"✓ Modello salvato in '{output_dir}/model_adapter'")

    print("\n" + "="*60)
    print("✅ FINE-TUNING COMPLETATO!")
    print("="*60)
