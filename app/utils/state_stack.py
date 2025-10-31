def push_state(user_data, state):
    """Добавляет состояние в стек"""
    if "state_stack" not in user_data:
        user_data["state_stack"] = []
    user_data["state_stack"].append(state)
    # Логирование для отладки
    # print(f"Pushed state: {state}, stack: {user_data['state_stack']}")

def pop_state(user_data):
    """Извлекает состояние из стека"""
    if "state_stack" not in user_data or not user_data["state_stack"]:
        return None
    state = user_data["state_stack"].pop()
    # Логирование для отладки
    # print(f"Popped state: {state}, stack: {user_data['state_stack']}")
    return state

def clear_stack(user_data):
    """Очищает стек состояний"""
    user_data["state_stack"] = []
    # print("Cleared state stack")

def get_current_state(user_data):
    """Возвращает текущее состояние без извлечения"""
    if "state_stack" not in user_data or not user_data["state_stack"]:
        return None
    return user_data["state_stack"][-1]