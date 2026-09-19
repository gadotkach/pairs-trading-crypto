"""Топ-50 пар по доходности для вариантов A и B (полные таблицы)."""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

OUTPUT_FILE = 'pair_strategies_analysis.xlsx'
RESULT_FILE = 'top50_crypto.xlsx'

PERIODS = ['5_лет', '3_года', '1_год']
VARIANTS = ['A', 'B']

# Полный список колонок
COLS = [
    'Пара', 'Экстремумы',
    'Сделок', 'Отменено', 'Довнесений',
    'Старт X, монет', 'Финал X, монет',
    'Старт Y, монет', 'Финал Y, монет',
    'Внесено, $', 'Деньги в конце, $',
    'Налог, $', 'Комиссия, $', 'Заработано (после), $',
    'Доходность (после), %', 'Где деньги в конце',
]


def main():
    print("=" * 120)
    print("ТОП-50 ПАР ПО ДОХОДНОСТИ")
    print("=" * 120)

    all_results = {}

    for period in PERIODS:
        print()
        print("#" * 120)
        print("# ПЕРИОД: {}".format(period))
        print("#" * 120)

        for variant in VARIANTS:
            sheet = '{}_{}'.format(variant, period)
            try:
                df = pd.read_excel(OUTPUT_FILE, sheet_name=sheet)
            except Exception as e:
                print("Нет листа {}: {}".format(sheet, e))
                continue

            if df.empty:
                continue

            cols_use = [c for c in COLS if c in df.columns]
            df = df[cols_use].copy()

            df = df.sort_values('Доходность (после), %',
                                ascending=False).head(50).reset_index(drop=True)
            df.insert(0, '#', range(1, len(df) + 1))

            print()
            print("=" * 120)
            print("Вариант {} — ТОП-50".format(variant))
            print("=" * 120)
            print()

            with pd.option_context('display.max_rows', None,
                                   'display.max_columns', None,
                                   'display.width', 300,
                                   'display.max_colwidth', 25):
                print(df.to_string(index=False))

            print()
            print("  Сводка:")
            print("    Всего: {}".format(len(df)))
            print("    Средняя: {:.2f}%".format(df['Доходность (после), %'].mean()))
            print("    Медиана: {:.2f}%".format(df['Доходность (после), %'].median()))
            print("    Средн. экстремумы: {:.1f}".format(df['Экстремумы'].mean()))
            print("    Средн. сделок: {:.1f}".format(df['Сделок'].mean()))
            print("    Средн. отмен: {:.1f}".format(df['Отменено'].mean()))

            key = '{}_{}'.format(variant, period)
            all_results[key] = df

    print()
    print("=" * 120)
    print("Запись в {}".format(RESULT_FILE))
    print("=" * 120)

    with pd.ExcelWriter(RESULT_FILE, engine='openpyxl') as w:
        for sheet_name, df in all_results.items():
            df.to_excel(w, sheet_name=sheet_name[:31], index=False)

    print("OK: {}".format(RESULT_FILE))
    for k, v in all_results.items():
        print("  {}: {} строк".format(k, len(v)))


if __name__ == "__main__":
    main()
