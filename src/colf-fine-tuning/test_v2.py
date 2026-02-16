from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Categorie valide
CATEGORIE = [
    "Cibo/Spesa", "Trasporti", "Casa", "Sanità", "Vestiti", 
    "Abbonamenti", "Bar", "Cibo fuori", "Viaggi", "Festa/Eventi", 
    "Sport", "Regali", "Altro extra", "Lavoro", "Auto", "Intrattenimento"
]

model_name = 'Qwen/Qwen2.5-1.5B-Instruct'
v1_path = './model/checkpoint-504'
v2_path = './model_v2_final'

tokenizer = AutoTokenizer.from_pretrained(model_name)

print("🔄 Caricamento modelli...")
print(f"  V1: {v1_path}")
print(f"  V2: {v2_path}\n")

# ← FIX: Forza CPU invece di auto
device = "cpu"  # ← AGGIUNTO
print(f"📍 Dispositivo: {device}\n")

# Carica modelli SU CPU
base1 = AutoModelForCausalLM.from_pretrained(
    model_name, 
    torch_dtype=torch.float32, 
    device_map=device  # ← CAMBIATO da "auto" a device
)
model_v1 = PeftModel.from_pretrained(base1, v1_path)

base2 = AutoModelForCausalLM.from_pretrained(
    model_name, 
    torch_dtype=torch.float32, 
    device_map=device  # ← CAMBIATO da "auto" a device
)
model_v2 = PeftModel.from_pretrained(base2, v2_path)

print("✅ Modelli caricati\n")

def classify(model, transaction):
    template = f"""Classifica questa transazione in UNA categoria tra: {", ".join(CATEGORIE)}.

Transazione: {transaction}
Categoria:"""
    
    inputs = tokenizer(template, return_tensors='pt').to(device)  # ← CAMBIATO: sposta input su device
    outputs = model.generate(
        **inputs, 
        max_new_tokens=20, 
        temperature=0.1, 
        do_sample=False
    )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Estrai solo la categoria
    category = response.split("Categoria:")[-1].strip()
    
    # Pulisci eventuali caratteri extra
    for cat in CATEGORIE:
        if cat.lower() in category.lower():
            return cat
    
    return category

# Test casi CRITICI (le 3 categorie problematiche)
test_cases_critical = [
    # Cibo/Spesa (ingredienti, prodotti)
    ("Peperoni 3", "Cibo/Spesa"),
    ("Fagioli 2.5", "Cibo/Spesa"),
    ("Farina 2", "Cibo/Spesa"),
    ("Sapone 4", "Cibo/Spesa"),
    ("Latte 1.5", "Cibo/Spesa"),
    ("Detersivo 6", "Cibo/Spesa"),
    
    # Bar (bevande alcoliche, colazioni)
    ("Birra 4", "Bar"),
    ("Birrone 5", "Bar"),
    ("Vino 12", "Bar"),
    ("Colazione 3", "Bar"),
    ("Caffè e brioche 2.5", "Bar"),
    ("Aperitivo 8", "Bar"),
    
    # Cibo fuori (piatti completi, ristoranti)
    ("Pizza 15", "Cibo fuori"),
    ("Kebab 8", "Cibo fuori"),
    ("Grigliata 28", "Cibo fuori"),
    ("Cena Driutti 45", "Cibo fuori"),
    ("Cibo cinese 20", "Cibo fuori"),
    ("Sushi 40", "Cibo fuori"),
    
    # Casi CONTRASTIVI (più difficili)
    ("Farina per pizza 2.5", "Cibo/Spesa"),
    ("Pizza margherita 12", "Cibo fuori"),
    ("Caffè in polvere 5", "Cibo/Spesa"),
    ("Caffè al bar 1.2", "Bar"),
    ("Birra supermercato 1.5", "Cibo/Spesa"),
    ("Birra al pub 5", "Bar"),
]

# Test altre categorie (campione)
test_cases_other = [
    ("Benzina 50", "Auto"),
    ("Metro 1.5", "Trasporti"),
    ("Affitto 600", "Casa"),
    ("Farmacia 15", "Sanità"),
    ("Jeans 45", "Vestiti"),
    ("Netflix 12.99", "Abbonamenti"),
    ("Hotel 120", "Viaggi"),
    ("Compleanno 50", "Festa/Eventi"),
    ("Palestra 40", "Sport"),
    ("Regalo 35", "Regali"),
    ("Multa 50", "Altro extra"),
    ("Computer 600", "Lavoro"),
    ("Cinema 9", "Intrattenimento"),
]

print("="*80)
print("🔥 TEST CRITICI (Cibo/Spesa vs Bar vs Cibo fuori)")
print("="*80)

correct_v1_critical = 0
correct_v2_critical = 0

for transaction, expected in test_cases_critical:
    v1_result = classify(model_v1, transaction)
    v2_result = classify(model_v2, transaction)
    
    v1_correct = v1_result == expected
    v2_correct = v2_result == expected
    
    if v1_correct:
        correct_v1_critical += 1
    if v2_correct:
        correct_v2_critical += 1
    
    status = "🟢" if v2_correct and not v1_correct else ("🟡" if v2_correct else "🔴")
    
    print(f"\n{status} {transaction:30s} → Atteso: {expected}")
    print(f"   V1: {v1_result:20s} {'✅' if v1_correct else '❌'}")
    print(f"   V2: {v2_result:20s} {'✅' if v2_correct else '❌'}")

print("\n" + "="*80)
print("📊 TEST ALTRE CATEGORIE (verifica non-forgetting)")
print("="*80)

correct_v1_other = 0
correct_v2_other = 0

for transaction, expected in test_cases_other:
    v1_result = classify(model_v1, transaction)
    v2_result = classify(model_v2, transaction)
    
    v1_correct = v1_result == expected
    v2_correct = v2_result == expected
    
    if v1_correct:
        correct_v1_other += 1
    if v2_correct:
        correct_v2_other += 1
    
    status = "✅" if v2_correct else "❌"
    
    print(f"{status} {transaction:30s} → V1: {v1_result:20s} | V2: {v2_result:20s}")

# Risultati finali
print("\n" + "="*80)
print("📈 RISULTATI FINALI")
print("="*80)

total_v1 = correct_v1_critical + correct_v1_other
total_v2 = correct_v2_critical + correct_v2_other
total_cases = len(test_cases_critical) + len(test_cases_other)

print(f"\n🔥 CASI CRITICI (Cibo/Spesa, Bar, Cibo fuori):")
print(f"   V1: {correct_v1_critical}/{len(test_cases_critical)} ({correct_v1_critical/len(test_cases_critical)*100:.1f}%)")
print(f"   V2: {correct_v2_critical}/{len(test_cases_critical)} ({correct_v2_critical/len(test_cases_critical)*100:.1f}%)")
print(f"   Miglioramento: {correct_v2_critical - correct_v1_critical:+d} casi")

print(f"\n📊 ALTRE CATEGORIE:")
print(f"   V1: {correct_v1_other}/{len(test_cases_other)} ({correct_v1_other/len(test_cases_other)*100:.1f}%)")
print(f"   V2: {correct_v2_other}/{len(test_cases_other)} ({correct_v2_other/len(test_cases_other)*100:.1f}%)")
print(f"   Variazione: {correct_v2_other - correct_v1_other:+d} casi")

print(f"\n🎯 TOTALE:")
print(f"   V1: {total_v1}/{total_cases} ({total_v1/total_cases*100:.1f}%)")
print(f"   V2: {total_v2}/{total_cases} ({total_v2/total_cases*100:.1f}%)")

if total_v2 > total_v1:
    print(f"   ✅ Miglioramento: +{total_v2 - total_v1} casi!")
elif total_v2 == total_v1:
    print(f"   🟡 Nessun cambiamento")
else:
    print(f"   ⚠️  Peggioramento: {total_v2 - total_v1} casi")

print("="*80)