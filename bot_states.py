from aiogram.dispatcher.filters.state import State, StatesGroup


class Routing(StatesGroup):
    step1_get_code = State()  # Установка на ожидание кода
    step1_raspr = State()     # Обработка распределения по коду
    step2_get_code = State()
    step2_raspr = State()


class Step1(StatesGroup):
    malevich_begin = State()  # _begin также содержат задние!
    malevich_bot_cospaces = State()
    malevich_end = State()

    kazan_begin = State()
    kazan_cospaces = State()
    kazan_end = State()

    promobot_begin = State()
    promobot_end = State()

    orbion_begin = State()
    orbion_end = State()
    final = State()


class Step2(StatesGroup):
    ar_art_begin = State()
    ar_art_finddoctor = State()
    ar_art_end = State()

    ar_suit_begin = State()
    ar_suit_end = State()

    hoversurf_begin = State()
    hoversurf_cospaces = State()
    hoversurf_video = State()
    hoversurf_glass = State()
    hoversurf_end = State()

    ovision_begin = State()
    ovision_cospaces = State()
    ovision_video = State()
    ovision_end = State()

    motorica_begin = State()
    motorica_cospaces = State()
    motorica_video = State()
    motorica_end = State()

    true_false_begin = State()
    true_false_tellquestions = State()
    true_false_processanswer = State()
    true_false_winner = State()
