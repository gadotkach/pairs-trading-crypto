"""Аналитика пар с DOT: основная + 2 таблицы экстремумов."""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd

STRATEGY_FILE = 'pair_strategies_analysis.xlsx'
ANALYTICS_FILE = 'analytics_z.xlsx'
RESULT_FILE = 'dot_analysis.xlsx'


def main():
    print("=" * 140)
    print("АНАЛИТИКА ПАР С DOT")
    print("=" * 140)

    # ---------- 1. Основная таблица (все периоды, все варианты) ----------
    print()
    print("=" * 140)
    print("1. ОСНОВНАЯ ТАБЛИЦА — пары с DOT (сортировка по Изменение, %)")
    print("=" * 140)

    all_rows = []
    for variant in ['A', 'B']:
        for period in ['5_лет', '3_года', '1_год']:
            sheet = '{}_{}'.format(variant, period)
            try:
                df = pd.read_excel(STRATEGY_FILE, sheet_name=sheet)
            except Exception as e:
                print("Нет листа {}: {}".format(sheet, e))
                continue

            if df.empty:
                continue

            # Пары с DOT
            mask = df['Пара'].str.contains('DOT', case=False, na=False)
            sub = df[mask].copy()
            if sub.empty:
                continue

            sub['Вариант'] = variant
            all_rows.append(sub)

    if all_rows:
        main_df = pd.concat(all_rows, ignore_index=True)
        main_df = main_df.sort_values('Изменение, %', ascending=False).reset_index(drop=True)

        cols_main = ['Вариант', 'Период', 'Пара', 'Экстремумы', 'Сделок', 'Отменено',
                     'Старт X, монет', 'Финал X, монет',
                     'Старт Y, монет', 'Финал Y, монет',
                     'Изменение, %',
                     'Внесено, $', 'Деньги в конце, $',
                     'Заработано (после), $', 'Доходность (после), %',
                     'Где деньги в конце']
        cols_use = [c for c in cols_main if c in main_df.columns]
        main_df = main_df[cols_use]

        with pd.option_context('display.max_rows', None,
                               'display.max_columns', None,
                               'display.width', 400,
                               'display.max_colwidth', 25):
            print(main_df.to_string(index=False))

        print()
        print("Всего пар с DOT: {}".format(len(main_df)))

        # Сохранить в Excel
        with pd.ExcelWriter(RESULT_FILE, engine='openpyxl') as w:
            main_df.to_excel(w, sheet_name='DOT_main', index=False)
    else:
        print("Пар с DOT не найдено")
        main_df = pd.DataFrame()

    # ---------- 2. ZigZag 5% — по Уровней с повтором ----------
    print()
    print("=" * 140)
    print("2. ZIGZAG 5% — пары с DOT (сортировка по Уровней с повтором)")
    print("=" * 140)

    try:
        df5 = pd.read_excel(ANALYTICS_FILE, sheet_name='Analytics_Z')
    except Exception as e:
        print("Нет Analytics_Z: {}".format(e))
        df5 = pd.DataFrame()

    if not df5.empty:
        mask = df5['Пара'].str.contains('DOT', case=False, na=False)
        dot5 = df5[mask].copy()

        if 'Уровней с повтором' in dot5.columns:
            dot5 = dot5.sort_values(['Уровней с повтором', 'Экстремумы'],
                                    ascending=[False, False]).reset_index(drop=True)

        cols_5 = ['Период', 'Пара', 'Экстремумы',
                  'P max', 'P min', 'Шаг, %',
                  'Уровней с повтором', 'Последний повтор',
                  'min Z 5', 'max Z 5',
                  'Мин движение %', 'Макс движение %', 'Среднее движение %']
        cols_use_5 = [c for c in cols_5 if c in dot5.columns]

        with pd.option_context('display.max_rows', None,
                               'display.max_columns', None,
                               'display.width', 400,
                               'display.max_colwidth', 25):
            print(dot5[cols_use_5].to_string(index=False))

        print()
        print("Всего пар с DOT (5%): {}".format(len(dot5)))

        # Сохранить в Excel
        with pd.ExcelWriter(RESULT_FILE, engine='openpyxl', mode='a') as w:
            dot5[cols_use_5].to_excel(w, sheet_name='DOT_zigzag5', index=False)

    # ---------- 3. ZigZag 10% — по Уровней с повтором ----------
    print()
    print("=" * 140)
    print("3. ZIGZAG 10% — пары с DOT (сортировка по Уровней с повтором)")
    print("=" * 140)

    try:
        df10 = pd.read_excel(ANALYTICS_FILE, sheet_name='Analytics_Z_10')
    except Exception as e:
        print("Нет Analytics_Z_10: {}".format(e))
        df10 = pd.DataFrame()

    if not df10.empty:
        mask = df10['Пара'].str.contains('DOT', case=False, na=False)
        dot10 = df10[mask].copy()

        if 'Уровней с повтором' in dot10.columns:
            dot10 = dot10.sort_values(['Уровней с повтором', 'Экстремумы'],
                                      ascending=[False, False]).reset_index(drop=True)

        cols_10 = ['Период', 'Пара', 'Экстремумы',
                   'P max', 'P min', 'Шаг, %',
                   'Уровней с повтором', 'Последний повтор',
                   'min Z 10', 'max Z 10',
                   'Мин движение %', 'Макс движение %', 'Среднее движение %']
        cols_use_10 = [c for c in cols_10 if c in dot10.columns]

        with pd.option_context('display.max_rows', None,
                               'display.max_columns', None,
                               'display.width', 400,
                               'display.max_colwidth', 25):
            print(dot10[cols_use_10].to_string(index=False))

        print()
        print("Всего пар с DOT (10%): {}".format(len(dot10)))

        # Сохранить в Excel
        with pd.ExcelWriter(RESULT_FILE, engine='openpyxl', mode='a') as w:
            dot10[cols_use_10].to_excel(w, sheet_name='DOT_zigzag10', index=False)

    print()
    print("=" * 140)
    print("OK: {}".format(RESULT_FILE))
    print("  Листы: DOT_main, DOT_zigzag5, DOT_zigzag10")
    print("=" * 140)


if __name__ == "__main__":
    main()
