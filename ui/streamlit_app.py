import logging
import hashlib
import os
import streamlit as st

from app.version import DISPLAY_VERSION
from ui.api_client import ApiContractError, Stage2ApiClient, request_error_detail, resolve_api_base_url
from ui import local_settings
from ui.suggestion_controls import render_suggestion_buttons
from ui.version_info import load_version_information
from ui.authentication import access_token_from_user, identity_cache_scope, oidc_configuration_ready, production_api_origin_ready

BASE = resolve_api_base_url()
logger = logging.getLogger(__name__)
client = Stage2ApiClient(BASE)
st.set_page_config(page_title="Deutschpath Unified Agent", layout="wide")


def _save_api_credential(name: str, widget_key: str, result_key: str) -> None:
    value = st.session_state.get(widget_key, "")
    try:
        local_settings.save_credential(name, value)
    except ValueError as exc:
        st.session_state[result_key] = ("error", str(exc))
    except OSError:
        st.session_state[result_key] = ("error", "本机配置文件写入失败；现有配置未被替换。")
    else:
        st.session_state[result_key] = ("success", "已安全保存到项目根目录 .env；重启 FastAPI 后生效。")
    finally:
        st.session_state.pop(widget_key, None)


def _rename_session(user_id: str, session_id: str) -> None:
    try:
        session = client.rename_session(user_id, session_id, st.session_state.get("rename_session_title", ""))
    except Exception as exc:
        logger.warning("Session rename failed (%s)", type(exc).__name__)
        st.session_state.session_rename_result = ("error", request_error_detail(exc))
    else:
        st.session_state.session_rename_result = ("success", session["title"])


def _local_settings_allowed() -> bool:
    if os.getenv("DEUTSCHPATH_LOCAL_SETTINGS_ENABLED") != "1":
        return False
    try:
        host = st.context.headers.get("host", "")
    except Exception:
        return False
    hostname = host.rsplit(":", 1)[0].strip("[]").lower()
    return hostname in {"127.0.0.1", "localhost"}


def _render_api_settings() -> None:
    with st.expander("API Settings", expanded=False):
        st.caption("仅供本机工程调试使用；设置写入项目根目录的 Git 忽略文件 .env。此 Beta 不提供生产级密钥管理。")
        if not _local_settings_allowed():
            st.warning("密钥管理未启用。请通过 scripts/start_frontend.ps1 在 127.0.0.1 启动并从本机访问；不要对外网开放 Streamlit。")
            editable = False
        else:
            editable = True

        deepseek_status = local_settings.credential_status("DEEPSEEK_API_KEY")
        st.markdown("**DeepSeek**")
        st.write(f"本机配置：{'已配置' if deepseek_status['configured'] else '未配置'} · 来源：{deepseek_status['source']}")
        try:
            health = client.get_health()
        except Exception:
            health = None
        if health:
            model_name = health.get("llm_model") or "未设置（DeepSeek 默认模型）"
            st.write(f"后端 Provider：{health.get('llm_provider', '未知')} · 模型：{model_name}")
            if health.get("deepseek_config_source") == "process environment":
                st.warning("后端进程环境变量优先于 .env；保存到 .env 不会覆盖该值。请在启动后端的 PowerShell 中更新环境变量并重启。")
        else:
            st.info("无法读取后端配置状态；请确认 FastAPI 已启动。")

        if not editable:
            st.text_input("DeepSeek API Key", type="password", disabled=True, key="settings_deepseek_key")
            st.text_input("Tavily API Key", type="password", disabled=True, key="settings_tavily_key")
        else:
            st.text_input("DeepSeek API Key（留空不变；输入新值后保存）", type="password", key="settings_deepseek_key")
            st.button("保存 DeepSeek Key", key="save_deepseek_key", on_click=_save_api_credential,
                      args=("DEEPSEEK_API_KEY", "settings_deepseek_key", "deepseek_save_result"),
                      disabled=not bool(st.session_state.get("settings_deepseek_key", "")))
        deepseek_saved = st.session_state.pop("deepseek_save_result", None)
        if deepseek_saved:
            (st.success if deepseek_saved[0] == "success" else st.error)(deepseek_saved[1])
        deepseek_test = st.button("测试 DeepSeek 真实连接", key="test_deepseek", disabled=not editable)
        if deepseek_test:
            with st.spinner("正在向 DeepSeek 发送公开短问题…"):
                st.session_state.api_deepseek_test_result = local_settings.test_deepseek_connection()
        if result := st.session_state.get("api_deepseek_test_result"):
            st.write(f"DeepSeek：{result['status']} · {result['message']}")

        st.markdown("**Tavily**")
        tavily_status = local_settings.credential_status("TAVILY_API_KEY")
        st.write(f"本机配置：{'已配置' if tavily_status['configured'] else '未配置'} · 来源：{tavily_status['source']}")
        if editable:
            st.text_input("Tavily API Key（留空不变；输入新值后保存）", type="password", key="settings_tavily_key")
            st.button("保存 Tavily Key", key="save_tavily_key", on_click=_save_api_credential,
                      args=("TAVILY_API_KEY", "settings_tavily_key", "tavily_save_result"),
                      disabled=not bool(st.session_state.get("settings_tavily_key", "")))
        tavily_saved = st.session_state.pop("tavily_save_result", None)
        if tavily_saved:
            (st.success if tavily_saved[0] == "success" else st.error)(tavily_saved[1])
        tavily_test = st.button("测试 Tavily 真实搜索", key="test_tavily", disabled=not editable)
        if tavily_test:
            with st.spinner("正在执行公开搜索词测试…"):
                st.session_state.api_tavily_test_result = local_settings.test_tavily_connection()
        if result := st.session_state.get("api_tavily_test_result"):
            st.write(f"Tavily：{result['status']} · {result['message']} · 结果数：{result['result_count']}")


def _render_system_information() -> None:
    with st.expander("系统信息 · 版本更新", expanded=False):
        information = load_version_information()
        st.caption("设置 → 系统信息 → 版本更新")
        view = st.selectbox("信息内容", ["版本更新", "功能状态"], key="system_information_view")
        if view == "功能状态":
            st.markdown(str(information["features"]))
            return
        st.write(f"应用：{information['app_name']}")
        st.write(f"版本：{information['version']} · 状态：{information['status']}")
        st.markdown("**最新更新摘要**")
        st.markdown(str(information["latest_summary"]))
        releases = information["releases"]
        versions = [str(release["version"]) for release in releases]
        current_version = str(information["version"]).removeprefix("v")
        selected = st.selectbox(
            "历史版本记录",
            versions,
            index=versions.index(current_version) if current_version in versions else 0,
            key="version_history_selector",
        )
        release = next(item for item in releases if item["version"] == selected)
        st.markdown(str(release["markdown"]))
        st.markdown("**技术演进 · M01–M10**")
        for milestone in information["milestones"]:
            with st.expander(f"{milestone['id']} · {milestone['title']}", expanded=False):
                st.markdown("**解决的问题**")
                st.write(str(milestone["problem"]))
                st.markdown("**新增功能**")
                st.write(" · ".join(milestone["features"]))
                st.markdown("**主要技术栈**")
                st.write(" · ".join(milestone["technology"]))
                st.markdown("**核心调用链**")
                st.code(str(milestone["chain"]), language=None)
                st.caption(f"验收状态：{milestone['status']}")


def render_ocr_review(preview: dict, user_id: str, session_id: str) -> None:
    import pandas as pd

    st.text_area("OCR 原始文字（不可信输入）", preview["ocr"].get("raw_text", ""), disabled=True, key=f"ocr-raw-{preview['operation_id']}")
    st.caption("请核对每个字段。若图片中没有表格或识别不完整，请勿确认。若目标表不存在，确认后会创建固定结构的 biz_vocabulary 表。")
    frame = pd.DataFrame(preview["rows"], columns=["word", "meaning", "level"])
    edited = st.data_editor(frame, num_rows="dynamic", key=f"ocr-rows-{preview['operation_id']}")
    confirmed = st.checkbox("我已核对以上词汇，并确认必要时创建 biz_vocabulary 表及写入这些数据", key=f"ocr-confirm-check-{preview['operation_id']}")
    if st.button("确认并写入，然后查询验证", disabled=not confirmed, key=f"ocr-commit-{preview['operation_id']}"):
        rows = edited.fillna("").to_dict(orient="records")
        try:
            result = client.confirm_ocr(user_id, session_id, preview["operation_id"], rows)
        except Exception as exc:
            logger.exception("MCP database confirmation failed")
            st.error(f"写入或验证失败：{request_error_detail(exc)}")
        else:
            st.success(f"已写入并查询验证 {result['inserted_rows']} 条记录。操作编号：{result['operation_id']}")
            st.dataframe(pd.DataFrame(result["rows"]))


def _render_chat_message(message: dict[str, str]) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


st.title(f"Deutschpath Unified Agent · {DISPLAY_VERSION}")
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
api_user_id: str | None
if APP_ENV == "production":
    provider = os.getenv("DEUTSCHPATH_OIDC_PROVIDER", "auth0")
    try:
        secrets = st.secrets
        configured = oidc_configuration_ready(secrets, provider, production=True)
    except Exception:
        configured = False
    try:
        from importlib.util import find_spec
        auth_runtime_ready = find_spec("authlib") is not None
    except (ImportError, ValueError):
        auth_runtime_ready = False
    api_origin_ready = production_api_origin_ready(BASE)
    if not configured or not auth_runtime_ready or not api_origin_ready:
        st.error("生产登录尚未配置完整。请配置 Streamlit OIDC、Authlib 与安全的 API 内网地址后重启。")
        st.stop()
    try:
        logged_in = st.user.is_logged_in
    except Exception:
        logged_in = False
    if not logged_in:
        st.info("请使用组织登录继续。")
        if st.button("使用 OIDC 登录", key="oidc_login"):
            st.login(provider)
        st.stop()
    token = access_token_from_user(st.user)
    cache_scope = identity_cache_scope(st.user)
    if not token or not cache_scope:
        st.error("登录成功，但未取得可供 API 使用的可信身份或 Access Token。请重新登录或联系管理员。")
        if st.button("重新登录", key="oidc_relogin_missing_token"):
            st.logout()
        st.stop()
    if st.session_state.get("oidc_cache_scope") != cache_scope:
        for key in list(st.session_state):
            if key != "oidc_cache_scope":
                st.session_state.pop(key, None)
        st.session_state.oidc_cache_scope = cache_scope
    def _require_reauthentication() -> None:
        st.session_state["api_reauthentication_required"] = True
    client = Stage2ApiClient(BASE, access_token=token, on_unauthorized=_require_reauthentication)
    if st.session_state.get("api_reauthentication_required"):
        st.error("API 会话已过期或被拒绝。请重新登录后继续。")
        if st.button("退出并重新登录", key="oidc_reauth"):
            st.session_state.clear()
            st.logout()
        st.stop()
    with st.sidebar:
        st.caption("已通过组织账号登录")
        if st.button("退出登录", key="oidc_logout"):
            st.session_state.clear()
            st.logout()
    api_user_id = None
else:
    api_user_id = st.text_input("User ID", "demo-user").strip()
user_id = api_user_id
if APP_ENV != "production" and st.session_state.get("ui_user_id") != user_id:
    # Adapt the user-scoped cleanup from 03's ui/state.py to 04's state keys.
    for key in list(st.session_state):
        if key in {"session_id", "session_picker", "uploaded_attachment_fingerprints", "learning_profile", "ocr_upload_fingerprint", "ocr_staged_image", "ocr_preview", "m09_suggestions"} or key.startswith(("profile_", "ocr-")):
            st.session_state.pop(key, None)
    st.session_state.ui_user_id = user_id
if APP_ENV != "production" and not user_id:
    st.warning("请输入 User ID。")
    st.stop()

with st.sidebar:
    st.subheader("对话")
    st.checkbox("推荐后续问题（可随时关闭）", key="m09_suggestions_enabled", value=False)
    if st.button("＋ 新建会话", key="create_session"):
        try:
            session = client.create_session(user_id)
        except Exception as exc:
            logger.exception("Create-session request or contract failed")
            st.error(f"创建会话失败：{request_error_detail(exc)}")
        else:
            st.session_state.session_id = session["id"]
            st.session_state.session_picker = session["id"]
            st.rerun()
    all_sessions = []
    try:
        sessions = client.list_sessions(user_id)
    except Exception as exc:
        logger.exception("Session-list request or contract failed")
        st.error(f"无法加载会话列表：{request_error_detail(exc)}")
    else:
        all_sessions = sessions
        session_search = st.text_input("搜索会话", key="session_search", placeholder="按标题搜索")
        if session_search.strip():
            needle = session_search.strip().casefold()
            sessions = [item for item in sessions if needle in str(item.get("title", "")).casefold()]
        titles = {session["id"]: f"{session.get('title') or 'New Chat'} · {session['id'][:8]}" for session in sessions}
        st.session_state.setdefault("session_picker", st.session_state.get("session_id"))
        if st.session_state.session_picker not in titles:
            active_id = st.session_state.get("session_id")
            st.session_state.session_picker = active_id if active_id in titles else None
        selected = st.selectbox("选择会话", [None, *titles], format_func=lambda value: titles.get(value, "选择已有会话"), key="session_picker")
        if selected:
            st.session_state.session_id = selected
        elif not session_search.strip():
            st.session_state.pop("session_id", None)

        active_id = st.session_state.get("session_id")
        current = next((item for item in all_sessions if item["id"] == active_id), None)
        if current:
            if st.session_state.get("rename_session_id") != active_id:
                st.session_state.rename_session_id = active_id
                st.session_state.rename_session_title = current.get("title") or "New Chat"
            with st.expander("会话管理", expanded=False):
                with st.form("rename_session_form"):
                    st.text_input("会话标题", max_chars=100, key="rename_session_title")
                    st.form_submit_button("保存标题", on_click=_rename_session, args=(user_id, active_id))
                rename_result = st.session_state.pop("session_rename_result", None)
                if rename_result:
                    (st.success if rename_result[0] == "success" else st.error)(
                        "会话标题已保存。" if rename_result[0] == "success" else f"重命名失败：{rename_result[1]}"
                    )
                st.caption("归档与恢复尚未启用：当前会话表没有归档字段，需要先审阅单独的 Schema 迁移方案。")
        elif session_search.strip():
            st.caption("没有找到匹配标题的会话。")

    with st.expander("学习资料与最近记录"):
        refresh_profile = st.button("刷新学习资料")
        if refresh_profile or "learning_profile" not in st.session_state:
            try:
                profile = client.get_user_state(user_id)
            except Exception as exc:
                logger.exception("User-state request or contract failed")
                st.error(f"无法加载学习资料：{request_error_detail(exc)}")
            else:
                st.session_state.learning_profile = profile
                st.session_state.profile_sync = True
        profile = st.session_state.get("learning_profile")
        if profile is not None:
            if st.session_state.pop("profile_sync", False):
                for field in ("current_level", "target_level", "learning_goal", "learning_preferences"):
                    st.session_state[f"profile_{field}"] = profile[field] or ""
            if st.session_state.pop("profile_saved", False):
                st.success("学习资料已保存。")
            levels = ["", "A1", "A2", "B1", "B2", "C1", "C2"]
            # Preserve any legacy value until the user explicitly changes it.
            levels += [profile[field] for field in ("current_level", "target_level") if profile[field] and profile[field] not in levels]
            with st.form("profile_form"):
                current_level = st.selectbox("当前等级", levels, format_func=lambda value: value or "未设置", key="profile_current_level")
                target_level = st.selectbox("目标等级", levels, format_func=lambda value: value or "未设置", key="profile_target_level")
                goal = st.text_area("学习目标", max_chars=2000, key="profile_learning_goal")
                preferences = st.text_area("学习偏好", max_chars=2000, key="profile_learning_preferences")
                save_profile = st.form_submit_button("保存学习资料")
            if save_profile:
                values = {"current_level": current_level or None, "target_level": target_level or None,
                          "learning_goal": goal.strip() or None, "learning_preferences": preferences.strip() or None}
                changes = {field: value for field, value in values.items() if value != profile[field]}
                if not changes:
                    st.info("学习资料没有变化。")
                else:
                    try:
                        saved = client.update_user_state(user_id, changes)
                    except Exception as exc:
                        logger.exception("User-state update request or contract failed")
                        st.error(f"学习资料保存失败：{request_error_detail(exc)}")
                    else:
                        st.session_state.learning_profile = saved
                        st.session_state.profile_sync = True
                        st.session_state.profile_saved = True
                        st.rerun()
        st.caption("最近 10 条学习记录")
        try:
            events = client.list_learning_events(user_id, limit=10)
        except Exception as exc:
            logger.exception("Learning-events request or contract failed")
            st.error(f"无法加载学习记录：{request_error_detail(exc)}")
        else:
            if not events:
                st.caption("暂无学习记录。")
            for event in events:
                st.text(f"{event['created_at']} · {event['event_type']}\n{event['item']}\n{event.get('result') or '—'}")

session_id = st.session_state.get("session_id")
if session_id:
    selected_session = next((item for item in all_sessions if item["id"] == session_id), None)
    st.header(selected_session.get("title") if selected_session else "当前会话")
    st.caption(f"会话 ID：{session_id}")
    with st.sidebar:
        with st.expander("学习资料与文件", expanded=False):
            uploaded_file = st.file_uploader("上传 TXT / MD / PDF / DOCX", type=["txt", "md", "pdf", "docx"], key=f"upload-{session_id}")
            if uploaded_file is not None:
                content = uploaded_file.getvalue()
                fingerprint = f"{session_id}:{uploaded_file.name}:{hashlib.sha256(content).hexdigest()}"
                uploaded = st.session_state.setdefault("uploaded_attachment_fingerprints", set())
                if fingerprint not in uploaded:
                    try:
                        attachment = client.upload_attachment(user_id, session_id, uploaded_file.name, content, uploaded_file.type or "application/octet-stream")
                    except ApiContractError:
                        logger.exception("Upload response contract is invalid")
                        st.error("文件上传失败：后端返回格式异常。")
                    except Exception as exc:
                        logger.exception("Upload request failed")
                        st.error(f"文件上传失败：{request_error_detail(exc)}")
                    else:
                        uploaded.add(fingerprint)
                        st.success(f"上传成功：{attachment['filename']} · 解析 {attachment.get('characters', '未知')} 字符")

        with st.expander("图片 OCR 与词汇入库", expanded=False):
            st.caption("识别结果是待核对候选；确认前不会写入业务数据库。")
            image_file = st.file_uploader("上传英语或德语表格图片", type=["png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"], key=f"ocr-upload-{session_id}")
            if image_file is not None:
                image_bytes = image_file.getvalue()
                fingerprint = hashlib.sha256(image_bytes).hexdigest()
                prior = st.session_state.get("ocr_upload_fingerprint")
                if prior != f"{session_id}:{fingerprint}":
                    try:
                        staged = client.upload_ocr_image(user_id, session_id, image_file.name, image_bytes, image_file.type or "application/octet-stream")
                    except Exception as exc:
                        logger.exception("OCR image upload failed")
                        st.error(f"图片上传失败：{request_error_detail(exc)}")
                    else:
                        st.session_state.ocr_upload_fingerprint = f"{session_id}:{fingerprint}"
                        st.session_state.ocr_staged_image = staged
                        st.session_state.pop("ocr_preview", None)
            staged = st.session_state.get("ocr_staged_image")
            if staged and st.session_state.get("ocr_upload_fingerprint", "").startswith(f"{session_id}:"):
                language = st.selectbox("识别语言", ["de", "en"], format_func=lambda value: "德语" if value == "de" else "英语", key=f"ocr-language-{session_id}")
                if st.button("识别并生成待审核候选", key=f"ocr-preview-{session_id}"):
                    try:
                        preview_result = client.preview_ocr(user_id, session_id, staged["image_id"], language)
                        preview_result["session_id"] = session_id
                        st.session_state.ocr_preview = preview_result
                    except Exception as exc:
                        logger.exception("MCP OCR preview failed")
                        st.error(f"OCR 失败：{request_error_detail(exc)}")
    preview = st.session_state.get("ocr_preview")
    if preview and preview.get("session_id") == session_id:
        if preview.get("success"):
            render_ocr_review(preview, user_id, session_id)
        else:
            st.error(preview.get("error", "未能生成可审核的候选表格。"))
            if preview.get("ocr", {}).get("raw_text"):
                st.text_area("OCR 原始文字（不可信输入）", preview["ocr"]["raw_text"], disabled=True, key=f"ocr-raw-failed-{preview.get('operation_id', 'unknown')}")
    try:
        messages = client.get_messages(user_id, session_id)
    except ApiContractError:
        logger.exception("Chat history response contract is invalid")
        st.error("聊天历史返回格式异常，请检查后端 API。")
        messages = []
    except Exception:
        logger.exception("Chat history request failed")
        st.error("无法加载聊天历史，请检查后端 API。")
        messages = []
    for message in messages:
        _render_chat_message(message)
    if not st.session_state.get("m09_suggestions_enabled", False):
        st.session_state.pop("m09_suggestions", None)
    else:
        session_suggestions = st.session_state.get("m09_suggestions", {}).get(session_id, [])
        render_suggestion_buttons(st, session_suggestions, session_id)
    if content := st.chat_input(
        "Ask about German or your uploaded material", key="chat_input", submit_mode="disable"
    ):
        # Render the submitted turn in this run. The next run will load the same
        # persisted records from the API, so nothing is echoed from session state.
        _render_chat_message({"role": "user", "content": content})
        send_result = None
        send_error = None
        st.session_state.setdefault("m09_suggestions", {}).pop(session_id, None)
        with st.chat_message("assistant"):
            with st.spinner("正在处理，请稍候…"):
                try:
                    if st.session_state.get("m09_suggestions_enabled", False):
                        send_result = client.send_message(
                            user_id, session_id, content, include_suggestions=True,
                        )
                    else:
                        # Preserve the legacy client call shape while the opt-in is off.
                        send_result = client.send_message(user_id, session_id, content)
                except Exception as exc:
                    send_error = exc
                    logger.warning("Send-message request failed (%s)", type(exc).__name__)
            if send_error is not None:
                # A timed-out POST may still finish on the backend. Read this
                # session once; never blindly replay a non-idempotent POST.
                try:
                    recovered = client.get_messages(user_id, session_id)
                except Exception as history_exc:
                    logger.warning("Chat-history recovery failed (%s)", type(history_exc).__name__)
                    recovered = []
                new_messages = recovered[len(messages):] if len(recovered) >= len(messages) else []
                matching_user = any(
                    item["role"] == "user" and item["content"] == content
                    for item in new_messages
                )
                recovered_assistant = next(
                    (item for item in reversed(new_messages) if item["role"] == "assistant"), None
                )
                if recovered_assistant and matching_user:
                    st.markdown(recovered_assistant["content"])
                    st.caption("已从当前会话历史恢复本次回复。")
                else:
                    st.error(request_error_detail(send_error))
                    if matching_user:
                        st.caption("用户消息已保存；助手回复尚未出现在会话历史中。为避免重复提交，本次未自动重发。")
                    elif isinstance(send_error, ApiContractError):
                        st.caption("后端可能已处理请求；请先查看当前会话历史，再决定是否重试。")
            else:
                if send_result.get("tool_operation") is not None:
                    operation = send_result["tool_operation"]
                    operation.setdefault("session_id", session_id)
                    st.session_state.ocr_preview = operation
                st.markdown(send_result["assistant_message"]["content"])
                suggestions = send_result.get("suggestions", [])
                if suggestions and st.session_state.get("m09_suggestions_enabled", False):
                    st.session_state.setdefault("m09_suggestions", {})[session_id] = suggestions[:3]
        if send_result is not None and send_result.get("tool_operation") is not None:
            # OCR review controls are rendered from session state on the next run.
            st.rerun()
        if send_result is not None and st.session_state.get("m09_suggestions", {}).get(session_id):
            st.rerun()

with st.sidebar:
    _render_api_settings()
    _render_system_information()
