# Python 3.10 required

from aiogram import Bot, Dispatcher, executor
from aiogram.types import (Message, CallbackQuery,
                           InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from asyncio import sleep
from bot_messages import BOT_MSGS, TRUE_FALSE_QUEST
import logging
from configparser import ConfigParser


CONF = ConfigParser()
CONF.read('config.cfg')

MSG_INT = int(CONF.get('Params', 'msg_interval', fallback=4))

# To divide children into groups with their own routes
STEP1_ROUTES = {                # Keys - inputted codes
    '1567': (1, 2, 3, 4, 0),    # Values - tuple of locations:
    '2784': (2, 3, 4, 1, 0),    # 1 - Malevich, 2 - Kazan, 3 - Promobot, 4 - Orbion
    '3048': (3, 4, 1, 2, 0),    # 0 - End of step
    '4650': (4, 1, 2, 3, 0),
}
STEP2_ROUTES = {
    '8956': (1, 4, 2, 3, 5, 6, 0),  # 1 - AR Paintings, 2 - HOVERSURF, 3 - OVISION
    '9568': (2, 3, 4, 5, 6, 1, 0),  # 4 - True/False game , 5 - Motor, 6 - AR Suit
    '5689': (3, 5, 1, 6, 4, 2, 0),
    '6895': (5, 1, 6, 2, 3, 4, 0),
}

# To store True/False game results
# { chat_id: { question_code: status } }
TRUE_FALSE_SCORE: dict[str, dict[str, None or True | False]] = {}

BOT = Bot(token=CONF.get('Bot', 'secret_key'))
DP = Dispatcher(BOT, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)


class Routing(StatesGroup):
    step1_get_code = State()    # Code waiting
    step1_route = State()       # Routing process
    step2_get_code = State()
    step2_route = State()


class Step1(StatesGroup):
    malevich_begin = State()
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
    ar_art_begin = State()  # *_begin also contain tasks!
    ar_art_find_doctor = State()
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
    true_false_tell_questions = State()
    true_false_process_answer = State()
    true_false_winner = State()


async def send_msgs(message: Message, key: str):
    for i, msg_or_delay in enumerate(BOT_MSGS[key]):
        is_msg = type(msg_or_delay) == str

        if i != 0 and type(BOT_MSGS[key][i - 1]) != int:    # To prevent double delay
            await sleep(MSG_INT if is_msg else msg_or_delay)

        if is_msg:
            await message.answer(msg_or_delay)


async def next_loc(state: FSMContext, new_step=False):
    async with state.proxy() as data:
        if new_step:
            data['loc'] = 0
        else:
            data['loc'] += 1


# Determining the next level (location) by its number, game part and route code:
@DP.callback_query_handler(text='yes', state=(Routing.step1_route, Routing.step2_route))
async def route(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    queue = data['loc']
    code = data['route']

    await call.message.answer('Вычисляю маршрут...')
    cur_state = await state.get_state()

    if cur_state == Routing.step1_route.state:
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

    if cur_state == Routing.step2_route.state:
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
                await sleep(MSG_INT)
                await call.message.answer('Готовы? Спутник, мотор, поехали…')
                return

    await sleep(MSG_INT)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Вперед!', callback_data='loc'))

    await call.message.answer('Нашел!', reply_markup=keyboard)


# ----------------[FIRST STEP]----------------
# Does it worth  to prevent accident restart?
@DP.message_handler(commands='start', state='*')
async def start(message: Message, state: FSMContext):
    await send_msgs(message, 'start')
    await Routing.step1_get_code.set()


# Getting the route code to start the first part and splitting into groups by routes:
@DP.message_handler(text=STEP1_ROUTES.keys(), state=Routing.step1_get_code)
async def step1_get_code(message: Message, state: FSMContext):
    await state.update_data(route=message.text.replace('\n', ' '))
    await next_loc(state, new_step=True)

    await send_msgs(message, 'step1_get_code')

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Да!', callback_data='yes'))

    await message.answer('Готовы?', reply_markup=keyboard)
    await Routing.step1_route.set()


# ----------------[Malevich]----------------
@DP.callback_query_handler(text='loc', state=Step1.malevich_begin)
async def malevich_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'malevich_begin')
    await Step1.malevich_bot_cospaces.set()


malevich_w = ('малевич', 'Малевич', 'malevich', 'Malevich')


@DP.message_handler(text=malevich_w, state=Step1.malevich_bot_cospaces)
async def malevich_bot_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'malevich_bot_cospaces')
    await Step1.malevich_end.set()


@DP.message_handler(text='0798', state=Step1.malevich_end)
async def malevich_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Поехали!', callback_data='yes'))

    await message.answer('Ура! Спешим дальше!', reply_markup=keyboard)

    await next_loc(state)
    await Routing.step1_route.set()


# ----------------[Kazan]----------------
@DP.callback_query_handler(text='loc', state=Step1.kazan_begin)
async def kazan_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'kazan_begin')
    await Step1.kazan_cospaces.set()


core_w = ('1', '2', '1 ядро', '2 ядро', '1 Ядро', '2 Ядро')


@DP.message_handler(text=core_w, state=Step1.kazan_cospaces)
async def kazan_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'kazan_cospaces')
    await Step1.kazan_end.set()


@DP.message_handler(text='4948', state=Step1.kazan_end)
async def kazan_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

    await message.answer('Отлично! Данные расшифрованы. Вместе с вами мы пройдём всё.',
                         reply_markup=keyboard)
    await next_loc(state)
    await Routing.step1_route.set()


# ----------------[Promobot]----------------
@DP.callback_query_handler(text='loc', state=Step1.promobot_begin)
async def promobot_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'promobot_begin')
    await Step1.promobot_end.set()


promobot_w = ('промобот', 'Промобот', 'ПРОМОБОТ', 'promobot', 'Promobot', 'PROMOBOT')


@DP.message_handler(text=promobot_w, state=Step1.promobot_end)
async def promobot_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

    await message.answer('Расшифровал! Ещё одна часть ключа: 5',
                         reply_markup=keyboard)
    await next_loc(state)
    await Routing.step1_route.set()


# ----------------[Orbion]----------------
@DP.callback_query_handler(text='loc', state=Step1.orbion_begin)
async def orbion_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'orbion_begin')
    await Step1.orbion_end.set()


orbion_w = ('орбион', 'Орбион', 'orbion', 'Orbion')


@DP.message_handler(text=orbion_w, state=Step1.orbion_end)
async def orbion_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

    await message.answer('Все верно! Я нашел еще одну часть ключа: 6',
                         reply_markup=keyboard)

    await next_loc(state)
    await Routing.step1_route.set()


@DP.callback_query_handler(text='loc', state=Step1.final)
async def step1_final(call: CallbackQuery, state: FSMContext):
    await call.message.answer(
        'Теперь чтобы я подключился к сети Сколково вам нужно ввести все части ключа в '
        'той последовательности, что вы получили.'
    )
    await sleep(MSG_INT)
    await Routing.step2_get_code.set()


# ----------------[SECOND STEP]----------------
@DP.message_handler(text=STEP2_ROUTES.keys(), state=Routing.step2_get_code)
async def step2_get_code(message: Message, state: FSMContext):
    await state.update_data(route=message.text)
    await next_loc(state, new_step=True)

    await message.answer('Я смог подключиться к сети Сколково и кое-что узнать.')
    await sleep(MSG_INT)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Да!', callback_data='yes'))

    await message.answer('Ты готов?', reply_markup=keyboard)
    await Routing.step2_route.set()


# ----------------[AR Paintings]----------------
@DP.callback_query_handler(text='loc', state=Step2.ar_art_begin)
async def ar_art_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'ar_art_begin')
    await Step2.ar_art_find_doctor.set()


pic1_w = ('окно в прошлое', 'Окно в прошлое', 'ОКНО В ПРОШЛОЕ')


@DP.message_handler(text=pic1_w, state=Step2.ar_art_find_doctor)
async def ar_art_finddoctor(message: Message, state: FSMContext):
    await send_msgs(message, 'ar_art_find_doctor')
    await Step2.ar_art_end.set()


pic2_w = ('физика света', 'Физика света', 'ФИЗИКА СВЕТА')


@DP.message_handler(text=pic2_w, state=Step2.ar_art_end)
async def ar_art_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

    await message.answer('Ура! Теперь наша машина времени сможет взлететь!',
                         reply_markup=keyboard)
    await next_loc(state)
    await Routing.step2_route.set()


# ----------------[AR Suit]----------------
@DP.callback_query_handler(text='loc', state=Step2.ar_suit_begin)
async def ar_suit_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'ar_suit_begin')
    await Step2.ar_suit_end.set()


firefighter_w = ('пожарный', 'Пожарный')


@DP.message_handler(text=firefighter_w, state=Step2.ar_suit_end)
async def ar_suit_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

    await message.answer(
        'Отлично! Жизненно необходимая профессия - Пожарный! Совершенно верно!',
        reply_markup=keyboard
    )
    await next_loc(state)
    await Routing.step2_route.set()


# ----------------[HOVERSURF]----------------
@DP.callback_query_handler(text='loc', state=Step2.hoversurf_begin)
async def hoversurf_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'hoversurf_begin')
    await Step2.hoversurf_cospaces.set()


hoversurf_w = ('ховерсерф', 'Ховерсерф', 'хуверсерф', 'Хуверсерф',
               'hoversurf', 'Hoversurf', 'HOVERSURF')


@DP.message_handler(text=hoversurf_w, state=Step2.hoversurf_cospaces)
async def hoversurf_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'hoversurf_cospaces')
    await Step2.hoversurf_video.set()


@DP.message_handler(text='2354', state=Step2.hoversurf_video)
async def hoversurf_video(message: Message, state: FSMContext):
    await send_msgs(message, 'hoversurf_video')
    await Step2.hoversurf_glass.set()


@DP.message_handler(text='2021', state=Step2.hoversurf_glass)
async def hoversurf_glass(message: Message, state: FSMContext):
    await send_msgs(message, 'hoversurf_glass')
    await Step2.hoversurf_end.set()


glass_w = ('термо глас', 'Термо глас', 'ТЕРМО ГЛАС')


@DP.message_handler(text=glass_w, state=Step2.hoversurf_end)
async def hoversurf_end(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

    await message.answer('Отлично ребята! Так держать!', reply_markup=keyboard)
    await next_loc(state)
    await Routing.step2_route.set()


# ----------------[OVISION]----------------
@DP.callback_query_handler(text='loc', state=Step2.ovision_begin)
async def ovision_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'ovision_begin')
    await Step2.ovision_cospaces.set()


@DP.message_handler(text='6776', state=Step2.ovision_cospaces)
async def ovision_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'ovision_cospaces')
    await Step2.ovision_video.set()


@DP.message_handler(text='1980', state=Step2.ovision_video)
async def ovision_video(message: Message, state: FSMContext):
    await send_msgs(message, 'ovision_video')
    await Step2.ovision_end.set()


@DP.message_handler(text='2', state=Step2.ovision_end)
async def ovision_end(message: Message, state: FSMContext):
    await message.answer('Запись данных прошла успешно')
    await sleep(MSG_INT/2)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

    await message.answer(
        'Ура-а-а! Теперь профессор сможет разблокировать всю систему в машине '
        'времени с помощью своего лица!',
        reply_markup=keyboard
    )
    await next_loc(state)
    await Routing.step2_route.set()


# ----------------[Motorica]----------------
@DP.callback_query_handler(text='loc', state=Step2.motorica_begin)
async def motorica_begin(call: CallbackQuery, state: FSMContext):
    await send_msgs(call.message, 'motorica_begin')
    await Step2.motorica_cospaces.set()


@DP.message_handler(text='5445', state=Step2.motorica_cospaces)
async def motorica_cospaces(message: Message, state: FSMContext):
    await send_msgs(message, 'motorica_cospaces')
    await Step2.motorica_video.set()


@DP.message_handler(text='2904', state=Step2.motorica_video)
async def _get_code(message: Message, state: FSMContext):
    await send_msgs(message, 'motorica_video')
    await Step2.motorica_end.set()


@DP.message_handler(text='3', state=Step2.motorica_end)
async def motorica_end(message: Message, state: FSMContext):
    await message.answer('Запись данных прошла успешно')
    await sleep(MSG_INT)

    await send_msgs(message, 'motorica_cospaces')

    await message.answer('Как же это здорово! '
                         'Эти роботы помогут нам быстро заменить сломанные детали!')
    await sleep(MSG_INT)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

    await message.answer(
        'Как я вам благодарен, что вы мне помогли восстановить систему и свою машину.',
        reply_markup=keyboard
    )
    await next_loc(state)
    await Routing.step2_route.set()


# ----------------[True/False game]----------------
@DP.callback_query_handler(text='loc', state=Step2.true_false_begin)
async def true_false_begin(call: CallbackQuery, state: FSMContext):
    TRUE_FALSE_SCORE[call.message.chat.id] = {}
    await send_msgs(call.message, 'true_false_begin')
    await Step2.true_false_tell_questions.set()


@DP.message_handler(text=TRUE_FALSE_QUEST.keys(), state=Step2.true_false_tell_questions)
async def true_false_tell_questions(message: Message, state: FSMContext):
    if TRUE_FALSE_SCORE[message.chat.id].get(message.text) is not None:
        await message.answer('Вы уже ответили на этот вопрос.')
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text='Правда', callback_data='tf_true:' + message.text))
    keyboard.add(InlineKeyboardButton(text='Ложь', callback_data='tf_false:' + message.text))

    await message.answer(TRUE_FALSE_QUEST[message.text][0], reply_markup=keyboard)
    await Step2.true_false_process_answer.set()


@DP.callback_query_handler(regexp=r'^(tf_true|tf_false)*', state=Step2.true_false_process_answer)
async def true_false_process_answer(call: CallbackQuery, state: FSMContext):
    user_answer, user_question_key = call.data.split(':')
    if TRUE_FALSE_SCORE[call.message.chat.id].get(user_question_key) is not None:
        return

    question = TRUE_FALSE_QUEST[user_question_key]
    if question[1] == (1 if user_answer == 'tf_true' else 0):
        TRUE_FALSE_SCORE[call.message.chat.id][user_question_key] = True
        await call.message.answer(question[2])
    else:
        TRUE_FALSE_SCORE[call.message.chat.id][user_question_key] = False
        await call.message.answer(question[3])

    if len(TRUE_FALSE_SCORE[call.message.chat.id]) < len(TRUE_FALSE_QUEST):
        await Step2.true_false_tell_questions.set()
        await call.message.answer("Жду следующий код")
    else:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text='Едем дальше', callback_data='yes'))

        await call.message.answer(
            'Друзья, вы большие молодцы! Не думал, что так быстро справитесь.',
            reply_markup=keyboard
        )
        await next_loc(state)
        await Routing.step2_route.set()


# ----------------[Default Answer]----------------
@DP.message_handler(lambda message: message.text, state='*')
async def process_invalid(message: Message):
    return await message.reply('Не все мои системы внорме, я не понял, что Вы сказали... '
                               'Возможно, Вы допустили ошибку.')


if __name__ == '__main__':
    executor.start_polling(DP, skip_updates=True)
