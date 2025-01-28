from asyncio import create_task, sleep, Event
from aiogram import Bot, Dispatcher, executor
from aiogram.types import (Message, CallbackQuery,
                           InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from bot_states import Routing, Step1, Step2, State
from bot_messages import BOT_MSGS, TRUE_FALSE_QUEST, MSG_T, HLP_NMBR
import logging
from configparser import ConfigParser


CONF = ConfigParser()
CONF.read('config.cfg')
DEBUG = True


MSG_T      # Тайминг между сообщениями (4)
HLP_NMBR   # Число доступных подсказок


# Для разбиения детей на группы со своими маршрутами 0-конец части:
STEP1_ROUTES = {              # Keys - вводимые коды
    '1567': (1, 2, 3, 4, 0),  # Values - маршруты:
    '2784': (2, 3, 4, 1, 0),  # 1-Малевич, 2-Казан, 3-Промобот, 4-Орбион
    '3048': (3, 4, 1, 2, 0),
    '4650': (4, 1, 2, 3, 0),
}
STEP2_ROUTES = {
    '8956': (1, 4, 2, 3, 5, 6, 0),  # 1-Картины AR,  2-HOVERSURF, 3-OVISION,
    '9568': (2, 3, 4, 5, 6, 1, 0),  # 4-Правда/Ложь, 5-Моторика,  6-Костюм AR
    '5689': (3, 5, 1, 6, 4, 2, 0),
    '6895': (5, 1, 6, 2, 3, 4, 0),
}


# Для установки ответов на вопросы
# { входное состояние: ответ) }:
ANSVERS: dict[str,  str] = {}


# Для подсчета результатов "Правда или Ложь"
# { id чата: { код вопроса: статус } }
TRUE_FALSE_SCORE: dict[str, dict[str, None or True | False]] = {}


# Тайминги для выполнения редиректа к AR костюмам:
REDIRECTS_TIME = {
    '1567': 5*60,
    '2784': 15*60,
    '3048': 30*60,
    '4650': 45*60,
}


BOT = Bot(token=CONF.get('Bot', 'secret_key'))
DP = Dispatcher(BOT, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)


# ----------------[ТЕХНИЧЕСКИЕ]----------------
async def send_msgs(obj: Message | CallbackQuery, key: str):
    if type(obj) == CallbackQuery:
        obj = obj.message
    for i, _msg in enumerate(BOT_MSGS[key]):
        switch = type(_msg) == str
        if i != 0 and type(BOT_MSGS[key][i - 1]) != int:
            await sleep(MSG_T if switch else _msg)
        if switch or DEBUG:
            await obj.answer(_msg)


async def next_loc(state: FSMContext, new_step=False):
    async with state.proxy() as data:
        if new_step:
            data['lvl'] = 0
        else:
            data['lvl'] += 1


# Должно применяться со сдвигом!
def set_answ(state: State, answer: str):
    ANSVERS[state.state] = answer


# ----------------[ПЕРЕАДРЕСАЦИЯ]----------------
if DEBUG:
    MSG_T = 0
    TIME_CHG = Event()  # Для отслеживания события промотки времени


async def redirecter(state: FSMContext, redirect_to: State):
    # Проверка, приступил ли пользователь к локации:
    try:
        if type((await state.get_data())['redir']) == bool:
            pass
    except KeyError:
        # Переадресация, если нет:
        await state.update_data(redir=await state.get_state())
        await send_msgs('redirect_start')
        await state.set_state(redirect_to.state)


async def reverse_redirecter(state: FSMContext, lvl_finished: bool):
    try:
        _ = (await state.get_data())['redir']
    except KeyError:
        await state.update_data(redir=lvl_finished)
        return

    if lvl_finished:
        redir = (await state.get_data())['redir']
        if type(redir) != bool:
            await state.set_state(redir)
            await send_msgs('redirect_back')


# async def group_timer(event: Event, route, state: FSMContext,
#                       redirect_to: State, time: int):
#     await sleep(time)
#     do = lambda: await redirect_processor(state, redirect_to)
#     do()
#     # # Пересчет пропуска времени для тестов:
#     # if event.is_set():
#     #     new_time = time - TIME_CHG
#     #     if new_time > 0:
#     #         await group_timer(event, route, state, redirect_to, new_time)
#     #     else:
#     #         do()


# ----------------[МАРШРУТИЗАЦИЯ]----------------
@DP.callback_query_handler(text='yes', state=(Routing.step1_raspr, Routing.step2_raspr))
async def router(call: CallbackQuery, state: FSMContext):
    # Определение следующего уровня (локации) по его номеру, части игры и коду маршрута:
    data = await state.get_data()
    queue = data['lvl']
    code = data['route']

    await call.message.answer('Вычисляю маршрут...')
    cur_state = await state.get_state()
    if cur_state == Routing.step1_raspr.state:
        match STEP1_ROUTES[code][queue]:
            case 1:
                await Step1.malevich_begin.set()
            case 2:
                await Step1.kazan_begin.set()
            case 3:
                await Step1.promobot_begin.set()
            case 4:
                await Step1.orbion_begin.set()
            case 0:
                await Step1.final.set()
    if cur_state == Routing.step2_raspr.state:
        match STEP2_ROUTES[code][queue]:
            case 1:
                await Step2.ar_art_begin.set()
            case 2:
                await Step2.hoversurf_begin.set()
            case 3:
                await Step2.ovision_begin.set()
            case 4:
                await Step2.true_false_begin.set()
            case 5:
                await Step2.motorica_begin.set()
            case 6:
                await Step2.ar_suit_begin.set()
            case 0:
                await call.message.answer('Ребята, у вас получилось! '
                                          'Но для начала вам нужно запустить систему.')
                await sleep(MSG_T)
                await call.message.answer('Готовы? Спутник, мотор, поехали…')
                await state.reset_state(with_data=True)
                return
    await sleep(MSG_T)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Вперед!', callback_data='loc'))
    await call.message.answer('Нашел!', reply_markup=keyboard)


# ----------------[ПЕРВАЯ ЧАСТЬ]----------------
@DP.message_handler(commands='start', state='*')
async def start(message: Message, state: FSMContext):
    await send_msgs(message, 'start')
    await state.update_data(helps=set())
    await next_loc(state, new_step=True)  # For debug
    await Routing.step1_get_code.set()


@DP.message_handler(text=STEP1_ROUTES.keys(), state=Routing.step1_get_code)
async def step1_get_route_code(message: Message, state: FSMContext):
    # Получение кода маршрута для разбиения на группы по маршрутам:
    route = message.text.replace('\n', ' ')
    await state.update_data(route=route)
    await next_loc(state, new_step=True)

    await send_msgs(message, 'step1_get_code')
    await send_msgs(message, 'help_start')

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Да!', callback_data='yes'))
    await message.answer('Готовы?', reply_markup=keyboard)
    await Routing.step1_raspr.set()

    # Установка таймера на переадресацию на AR костюмы:
    # create_task(group_timer(route, state, Step2.ar_suit_begin))


# ----------------[Малевич]----------------
@DP.callback_query_handler(text='loc', state=Step1.malevich_begin)
async def malevich_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'malevich_begin')
    await Step1.malevich_bot_cospaces.set()
set_answ(Step1.malevich_bot_cospaces, 'Малевич')


malevich_w = ('малевич', 'Малевич', 'malevich', 'Malevich')


@DP.message_handler(text=malevich_w, state=Step1.malevich_bot_cospaces)
async def malevich_bot_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'malevich_bot_cospaces')
    await Step1.malevich_end.set()
set_answ(Step1.malevich_end, '0798')


@DP.message_handler(text='0798', state=Step1.malevich_end)
async def malevich_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Поехали!', callback_data='yes'))
    await message.answer('Ура! Спешим дальше!', reply_markup=keyboard)
    await next_loc(state)
    await Routing.step1_raspr.set()


# ----------------[Казан]----------------
@DP.callback_query_handler(text='loc', state=Step1.kazan_begin)
async def kazan_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'kazan_begin')
    await Step1.kazan_cospaces.set()
set_answ(Step1.kazan_cospaces, '1 ядро')


core_w = ('1', '2', '1 ядро', '2 ядро', '1 Ядро', '2 Ядро')


@DP.message_handler(text=core_w, state=Step1.kazan_cospaces)
async def kazan_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'kazan_cospaces')
    await Step1.kazan_end.set()
set_answ(Step1.kazan_end, '4948')


@DP.message_handler(text='4948', state=Step1.kazan_end)
async def kazan_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
    await message.answer('Отлично! Данные расшифрованы. Вместе с вами мы пройдём всё.',
                         reply_markup=keyboard)
    await next_loc(state)
    await Routing.step1_raspr.set()


# ----------------[Промобот]----------------
@DP.callback_query_handler(text='loc', state=Step1.promobot_begin)
async def promobot_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'promobot_begin')
    await Step1.promobot_end.set()
set_answ(Step1.promobot_end, 'Промобот')


promobot_w = ('промобот', 'Промобот', 'ПРОМОБОТ', 'promobot', 'Promobot', 'PROMOBOT')


@DP.message_handler(text=promobot_w, state=Step1.promobot_end)
async def promobot_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
    await message.answer('Расшифровал! Ещё одна часть ключа: 5', reply_markup=keyboard)
    await next_loc(state)
    await Routing.step1_raspr.set()


# ----------------[Орбион]----------------
@DP.callback_query_handler(text='loc', state=Step1.orbion_begin)
async def orbion_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'orbion_begin')
    await Step1.orbion_end.set()
set_answ(Step1.orbion_end, 'Орбион')


orbion_w = ('орбион', 'Орбион', 'orbion', 'Orbion')


@DP.message_handler(text=orbion_w, state=Step1.orbion_end)
async def orbion_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
    await message.answer('Все верно! Я нашел еще одну часть ключа: 6',
                         reply_markup=keyboard)
    await next_loc(state)
    await Routing.step1_raspr.set()


@DP.callback_query_handler(text='loc', state=Step1.final)
async def step1_final(call: CallbackQuery, state: FSMContext):
    await call.message.answer(
        'Теперь чтобы я подключился к сети Сколково вам нужно ввести все части ключа в '
        'той последовательности, что вы получили.')
    await sleep(MSG_T)
    await Routing.step2_get_code.set()


# ----------------[ВТОРАЯ ЧАСТЬ]----------------
@DP.message_handler(text=STEP2_ROUTES.keys(), state=Routing.step2_get_code)
async def step2_get_route_code(message: Message, state: FSMContext):
    await state.update_data(route=message.text)
    await next_loc(state, new_step=True)

    await message.answer('Я смог подключиться к сети Сколково и кое-что узнать.')
    await sleep(MSG_T)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Да!', callback_data='yes'))
    await message.answer('Ты готов?', reply_markup=keyboard)
    await Routing.step2_raspr.set()


# ----------------[AR картины]----------------
@DP.callback_query_handler(text='loc', state=Step2.ar_art_begin)
async def ar_art_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'ar_art_begin')
    await Step2.ar_art_finddoctor.set()
set_answ(Step2.ar_art_finddoctor, 'Окно в прошлое')

pic1_w = ('окно в прошлое', 'Окно в прошлое', 'ОКНО В ПРОШЛОЕ')


@DP.message_handler(text=pic1_w, state=Step2.ar_art_finddoctor)
async def ar_art_finddoctor(message: Message, state: FSMContext):
    await send_msgs(message, 'ar_art_finddoctor')
    await Step2.ar_art_end.set()
set_answ(Step2.ar_art_end, 'Физика света')


pic2_w = ('физика света', 'Физика света', 'ФИЗИКА СВЕТА')


@DP.message_handler(text=pic2_w, state=Step2.ar_art_end)
async def ar_art_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
    await message.answer('Ура! Теперь наша машина времени сможет взлететь!',
                         reply_markup=keyboard)
    await next_loc(state)
    await Routing.step2_raspr.set()


# ----------------[AR костюм]----------------
@DP.callback_query_handler(text='loc', state=Step2.ar_suit_begin)
async def ar_suit_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'ar_suit_begin')
    await Step2.ar_suit_end.set()
set_answ(Step2.ar_suit_end, 'Пожарный')


firefighter_w = ('пожарный', 'Пожарный')


@DP.message_handler(text=firefighter_w, state=Step2.ar_suit_end)
async def ar_suit_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
    await message.answer(
        'Отлично! Жизненно необходимая профессия - Пожарный! Совершенно верно!',
        reply_markup=keyboard)
    await next_loc(state)
    await Routing.step2_raspr.set()


# ----------------[HOVERSURF]----------------
@DP.callback_query_handler(text='loc', state=Step2.hoversurf_begin)
async def hoversurf_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'hoversurf_begin')
    await Step2.hoversurf_cospaces.set()
set_answ(Step2.hoversurf_cospaces, 'Hoversurf')


hoversurf_w = ('ховерсерф', 'Ховерсерф', 'хуверсерф', 'Хуверсерф',
               'hoversurf', 'Hoversurf', 'HOVERSURF')


@DP.message_handler(text=hoversurf_w, state=Step2.hoversurf_cospaces)
async def hoversurf_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'hoversurf_cospaces')
    await Step2.hoversurf_video.set()
set_answ(Step2.hoversurf_video, '2354')


@DP.message_handler(text='2354', state=Step2.hoversurf_video)
async def hoversurf_video(message: Message, state: FSMContext):
    await send_msgs(message, 'hoversurf_video')
    await Step2.hoversurf_glass.set()
set_answ(Step2.hoversurf_glass, '2021')


@DP.message_handler(text='2021', state=Step2.hoversurf_glass)
async def hoversurf_glass(message: Message, state: FSMContext):
    await send_msgs(message, 'hoversurf_glass')
    await Step2.hoversurf_end.set()
set_answ(Step2.hoversurf_end, 'Термо глас')


glass_w = ('термо глас', 'Термо глас', 'ТЕРМО ГЛАС')


@DP.message_handler(text=glass_w, state=Step2.hoversurf_end)
async def hoversurf_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
    await message.answer('Отлично ребята! Так держать!', reply_markup=keyboard)
    await next_loc(state)
    await Routing.step2_raspr.set()


# ----------------[OVISION]----------------
@DP.callback_query_handler(text='loc', state=Step2.ovision_begin)
async def ovision_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'ovision_begin')
    await Step2.ovision_cospaces.set()
set_answ(Step2.ovision_cospaces, '6776')


@DP.message_handler(text='6776', state=Step2.ovision_cospaces)
async def ovision_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'ovision_cospaces')
    await Step2.ovision_video.set()
set_answ(Step2.ovision_video, '1980')


@DP.message_handler(text='1980', state=Step2.ovision_video)
async def ovision_video(message: Message, state: FSMContext):
    await send_msgs(message, 'ovision_video')
    await Step2.ovision_end.set()
set_answ(Step2.ovision_end, '2')


@DP.message_handler(text='2', state=Step2.ovision_end)
async def ovision_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
    await message.answer('Запись данных прошла успешно')
    await sleep(2)
    await message.answer(
        'Ура-а-а! Теперь профессор сможет разблокировать всю систему в машине '
        'времени с помощью своего лица!', reply_markup=keyboard)
    await next_loc(state)
    await Routing.step2_raspr.set()


# ----------------[Моторика]----------------
@DP.callback_query_handler(text='loc', state=Step2.motorica_begin)
async def motorica_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'motorica_begin')
    await Step2.motorica_cospaces.set()
set_answ(Step2.motorica_cospaces, '5445')


@DP.message_handler(text='5445', state=Step2.motorica_cospaces)
async def motorica_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'motorica_cospaces')
    await Step2.motorica_video.set()
set_answ(Step2.motorica_video, '2904')


@DP.message_handler(text='2904', state=Step2.motorica_video)
async def motorica_video(message: Message, state: FSMContext):
    await send_msgs(message, 'motorica_video')
    await Step2.motorica_end.set()
set_answ(Step2.motorica_end, '3')


@DP.message_handler(text='3', state=Step2.motorica_end)
async def motorica_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
    await message.answer('Запись данных прошла успешно')
    await sleep(MSG_T)
    await message.answer(
        'Как же это здорово! Эти роботы помогут нам быстро заменить сломанные детали!')
    await sleep(MSG_T)
    await message.answer(
        'Как я вам благодарен, что вы мне помогли восстановить систему и свою машину.',
        reply_markup=keyboard)
    await next_loc(state)
    await Routing.step2_raspr.set()


# ----------------[Правда или ложь]----------------
@DP.callback_query_handler(text='loc', state=Step2.true_false_begin)
async def true_false_begin(call: CallbackQuery, state: FSMContext):
    TRUE_FALSE_SCORE[call.message.chat.id] = {}
    await send_msgs(call.message, 'true_false_begin')
    await Step2.true_false_tellquestions.set()


@DP.message_handler(text=TRUE_FALSE_QUEST.keys(), state=Step2.true_false_tellquestions)
async def true_false_tellquestions(message: Message, state: FSMContext):
    if TRUE_FALSE_SCORE[message.chat.id].get(message.text) is not None:
        await message.answer('Вы уже ответили на этот вопрос.')
        return
    TRUE_FALSE_SCORE[message.chat.id][message.text] = None  # Для механизма подсказок

    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton(text='Правда', callback_data='tf_true:' + message.text),
        InlineKeyboardButton(text='Ложь', callback_data='tf_false:' + message.text)
    )
    keyboard.add()

    await message.answer(TRUE_FALSE_QUEST[message.text][0], reply_markup=keyboard)
    await Step2.true_false_processanswer.set()


@DP.callback_query_handler(regexp=r'(tf_true|tf_false):\d+$',
                           state=Step2.true_false_processanswer)
async def true_false_processanswer(obj: CallbackQuery, state: FSMContext):
    chat_id = obj.message.chat.id
    user_answer, user_question_key = obj.data.split(':')

    # Игнорирование нажатия кнопки уже отвеченного вопроса:
    if TRUE_FALSE_SCORE[chat_id].get(user_question_key) is not None:
        return

    # Обработка правильности ответа:
    question = TRUE_FALSE_QUEST[user_question_key]
    if question[1] == (True if user_answer == 'tf_true' else False):
        TRUE_FALSE_SCORE[chat_id][user_question_key] = True
        await obj.message.answer(question[2])
    else:
        TRUE_FALSE_SCORE[chat_id][user_question_key] = False
        await obj.message.answer(question[3])

    # Проверка на окончание игры:
    if len(TRUE_FALSE_SCORE[chat_id]) < len(TRUE_FALSE_QUEST):
        await obj.message.answer('Жду следующий код')
        await Step2.true_false_tellquestions.set()
    else:
        # Вывод результатов:
        await obj.message.answer(f'Фух, все!')

        total = len(TRUE_FALSE_QUEST)
        right = sum(result for result in TRUE_FALSE_SCORE[chat_id].values() if result)
        await obj.message.answer(f'Твой результат: {right}/{total}')

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))
        await obj.message.answer(
            'Друзья, вы большие молодцы! Не думал, что так быстро справитесь.',
            reply_markup=keyboard)

        await next_loc(state)
        await Routing.step2_raspr.set()


help_w = ('помощь', 'Помощь', 'подсказка', 'Подсказка',
          'помоги', 'Помоги', '/help',)


# ----------------[Обработка подсказки]----------------
@DP.callback_query_handler(regexp=r'help:*', state='*')
@DP.message_handler(text=help_w, state='*')
async def help(obj: Message | CallbackQuery, state: FSMContext):
    # Для общих подсказок сохраняется их ответ, который должен быть уникальным,
    # для правда/ложь сохраняется код вопроса

    async with state.proxy() as data:
        state_str = await state.get_state()
        is_tru_false = state_str == Step2.true_false_processanswer.state

        # Обработка запроса:
        if type(obj) == Message:
            # Определение ответа для подсказки:
            try:
                if is_tru_false:
                    last_question_key = list(TRUE_FALSE_SCORE[obj.chat.id])[-1]
                    answer = 'Правда' if TRUE_FALSE_QUEST[last_question_key][1] else 'Ложь'
                else:
                    answer = ANSVERS[state_str]

            # Возможно отсутствие подсказки:
            except KeyError:
                await obj.answer('Для этого места подсказка не доступна')
                return

            # Для повторного запроса:
            answer_key = last_question_key if is_tru_false else answer
            if answer_key in data['helps']:
                await obj.answer(BOT_MSGS['help_was_given'].format(answer))
                return

            # Запрос подтверждения/отказ:
            used_num = len(data['helps'])
            if used_num < HLP_NMBR:
                await obj.answer(BOT_MSGS['help_remained'].format(HLP_NMBR - used_num))
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(text='Да', callback_data=f'help:{answer_key}'))
                await obj.answer('Воспользоваться?', reply_markup=keyboard)
            else:
                await obj.answer(BOT_MSGS['help_no'])

        # Обработка подтверждения:
        else:
            # Получение ответа:
            answer_key = obj.data.split(':')[1]
            if is_tru_false:
                answer = 'Правда' if TRUE_FALSE_QUEST[answer_key][1] else 'Ложь'
            else:
                answer = answer_key

            # Проверка повторного запроса:
            if answer_key in data['helps']:
                await obj.answer(
                    (BOT_MSGS['help_was_given']
                     .replace('этот вопрос', f'вопрос "{TRUE_FALSE_QUEST[answer_key][0][:10]} ..."')
                     if is_tru_false else BOT_MSGS['help_was_given']).format(answer)
                )
                return

            # Проверка, что вопрос еще не отвечен:
            if is_tru_false and answer_key in TRUE_FALSE_SCORE[obj.chat.id]:
                return
            for st, ans in ANSVERS.items():
                if ans == answer and st != state_str:
                    return

            await obj.message.answer('Подсказка: ' + answer)
            data['helps'].add(answer_key if is_tru_false else answer)


# ----------------[Для тестирования]----------------
if DEBUG:
    loc_map_s1 = {
        1: 'Малевич',
        2: 'Казан',
        3: 'Промобот',
        4: 'Орбион',
        0: 'Конец'
    }
    loc_map_s2 = {
        1: 'Картины AR',
        2: 'HOVERSURF',
        3: 'OVISION',
        4: 'Правда/Ложь',
        5: 'Моторика',
        6: 'Костюм AR',
        0: 'Конец'
    }


    @DP.message_handler(commands='context', state='*')
    async def show_context(message: Message, state: FSMContext):
        await message.answer(f'Состояние: {await state.get_state()}\n'
                             f'Текущий контекст: {await state.get_data()}')


    @DP.message_handler(commands='step2', state='*')
    async def set_step2(message: Message, state: FSMContext):
        await message.answer('Вы перешли на второй этап.')
        await message.answer(
            'Теперь чтобы я подключился к сети Сколково вам нужно ввести все части ключа в '
            'той последовательности, что вы получили.')
        await Routing.step2_get_code.set()


    @DP.message_handler(commands='set_route', state='*')
    async def set_route(message: Message, state: FSMContext):
        arg = message.get_args()
        try:
            await state.update_data(route=arg)
            await message.answer(f'Установлен маршрут: {arg}')
        except:
            await message.answer(f'Правильно передайте аргумент')


    # Установка локации по ее номеру следования (начинается с 1)
    @DP.message_handler(commands='set_level', state='*')
    async def set_lvl(message: Message, state: FSMContext):
        try:
            lvl_num = int(message.get_args()) - 1  #
            route = (await state.get_data())['route']
            router, locationer = (STEP1_ROUTES, loc_map_s1) \
                if route in STEP1_ROUTES else (STEP2_ROUTES, loc_map_s2)
            await state.update_data(lvl=lvl_num)
            loc_key  = router[route][lvl_num]
            await message.answer(f'Переход на уровень №: {lvl_num + 1} '
                                 f'(код {loc_key} -> {locationer[loc_key]})')
        except:
            await message.answer(f'Правильно передайте аргумент')


    @DP.message_handler(commands='drop_helps', state='*')
    async def drop_helps(message: Message, state: FSMContext):
        await state.update_data(helps=set())
        await message.answer(f'У вас снова подсказок: ' + HLP_NMBR)


    @DP.message_handler(commands='skip_time', state='*')
    async def skip_time(message: Message, state: FSMContext):
        sec = int(message.get_args())


# ----------------[Дефолтный ответ]----------------
@DP.message_handler(lambda message: message.text, state='*')
async def process_invalid(message: Message):
    return await message.reply('Не все мои системы в норме, я не понял, что вы сказали. '
                               'Возможно вы допустили ошибку.')


if __name__ == '__main__':
    executor.start_polling(DP, skip_updates=True)
