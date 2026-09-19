"""Топ-100 по Изменение, %."""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

OUTPUT_FILE = 'pair_strategies_analysis.xlsx'
RESULT_FILE = 'top100_change.xlsx'

PERIODS = ['5_лет', '3_года', '1_год']
VARIANTS = ['A', 'B']

# БЕЗ Продано/Куплено
COLS = [
    'Пара', 'Экстремумы',
    'Сделок', 'Отменено', 'Довнесений',
    'Старт X, монет', 'Финал X, монет',
    'Старт Y, монет', 'Финал Y, монет',
    'Изменение, %',
    'Внесено, $', 'Деньги в конце, $',
    'Заработано (после), $', 'Доходность (после), %',
    'Где деньги в конце',
]


def main():
    print("=" * 140)
    print("ТОП-100 ПО ИЗМЕНЕНИЮ, %")
    print("=" * 140)

    all_results = {}

    for period in PERIODS:
        print()
        print("#" * 140)
        print("# ПЕРИОД: {}".format(period))
        print("#" * 140)

        for variant in VARIANTS:
            sheet = '{}_{}'.format(variant, period)
            try:
                df = pd.read_excel(OUTPUT_FILE, sheet_name=sheet)
            except Exception as e:
                print("Нет листа {}: {}".format(sheet, e))
                continue

            if df.empty or 'Изменение, %' not in df.columns:
                continue

            df = df.dropna(subset=['Изменение, %']).copy()
            if df.empty:
                continue

            cols_use = [c for c in COLS if c in df.columns]
            df = df[cols_use].copy()

            df = df.sort_values('Изменение, %', ascending=False).head(100).reset_index(drop=True)
            df.insert(0, '#', range(1, len(df) + 1))

            print()
            print("=" * 140)
            print("Вариант {} — ТОП-100".format(variant))
            print("=" * 140)
            print()

            with pd.option_context('display.max_rows', None,
                                   'display.max_columns', None,
                                   'display.width', 400,
                                   'display.max_colwidth', 25):
                print(df.to_string(index=False))

            key = '{}_{}'.format(variant, period)
            all_results[key] = df

    print()
    print("Запись в {}".format(RESULT_FILE))

    with pd.ExcelWriter(RESULT_FILE, engine='openpyxl') as w:
        for sheet_name, df in all_results.items():
            df.to_excel(w, sheet_name=sheet_name[:31], index=False)

    print("OK: {}".format(RESULT_FILE))
    for k, v in all_results.items():
        print("  {}: {} строк".format(k, len(v)))


if __name__ == "__main__":
    main()
