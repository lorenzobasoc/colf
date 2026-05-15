from datasets import load_dataset
from functions import _log_test_result, generate, load_model
import random

MODEL_NAME="Qwen/Qwen3.5-2B"
USE_FINE_TUNED_MODEL=False
LORA_ADAPTER_PATH=""
TESTING_DATA_PATH="training_data/train_data_focused.jsonl"

def train(model, tokenizer):
    print()

def test(model, tokenizer, test_cases):
    testing_data = load_dataset('json', data_files=TESTING_DATA_PATH)['train']
    test_indices = random.sample(range(len(testing_data)), min(test_cases, len(testing_data)))

    for idx in test_indices:
        instruction = testing_data['instruction'][idx]
        expected = testing_data['response'][idx]
        actual = generate(model, instruction, tokenizer)

        _log_test_result(idx, instruction, expected, actual)




def main():
    (model, tokenizer) = load_model(MODEL_NAME, USE_FINE_TUNED_MODEL, LORA_ADAPTER_PATH)

    # train(model, tokenizer)

    test(model, tokenizer, 30)


if __name__ == "__main__":
    main()