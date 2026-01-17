import asyncio
import sys
import traceback
from .modules.expenses.expense_agent import run_expense_agent

async def main():
    try:
        await run_expense_agent()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
