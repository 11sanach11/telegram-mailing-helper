'use strict';

// ============================================================
// TypeScript-style type definitions (JSDoc)
// ============================================================

/**
 * @typedef {{ id: number, dispatch_group_name: string, description: string, enabled: boolean, show_group_only_for: string|null }} GroupNameInfo
 * @typedef {{ id: number, dispatch_group_name: string, description: string, enabled: boolean, priority: number, repeat: number, count: number, assigned_count: number, free_count: number, show_comment_with_block: boolean|number, show_count_of_taken_blocks: boolean|number, show_group_only_for: string|null }} GroupInfo
 * @typedef {{ info: GroupInfo, state: { text: string, value: string } }} GroupDetail
 * @typedef {{ id: number, telegram_id: string, name: string, state: string, localizedState: string, created: string }} UserItem
 * @typedef {{ key: string, value: string, description: string }} StorageItem
 * @typedef {{ key: string, title: string, data: string }} ReportItem
 */

const { createApp, ref, reactive, computed, onMounted } = Vue;
const { createRouter, createWebHashHistory } = VueRouter;

// ============================================================
// API client
// ============================================================

/**
 * @param {string} method
 * @param {string} url
 * @param {object|null} body
 * @returns {Promise<any>}
 */
async function apiCall(method, url, body) {
  const headers = {};
  if (body !== null && body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  const resp = await fetch(url, {
    method,
    headers,
    credentials: 'same-origin',
    body: body != null ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 401) {
    window.location.reload();
    return null;
  }
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText);
    throw new Error('HTTP ' + resp.status + ': ' + text);
  }
  const text = await resp.text();
  return text ? JSON.parse(text) : null;
}

const api = {
  /** @param {string} url @returns {Promise<any>} */
  get: (url) => apiCall('GET', url, null),
  /** @param {string} url @param {object} body @returns {Promise<any>} */
  post: (url, body) => apiCall('POST', url, body),
};

// ============================================================
// AppHeader
// ============================================================

const AppHeader = {
  setup() {
    const botName = ref('...');
    const menuOpen = ref(false);

    const navLinks = [
      { to: '/users', label: 'Пользователи' },
      { to: '/dispatch_lists', label: 'Редактирование списков' },
      { to: '/settings', label: 'Настройки' },
      { to: '/reports', label: 'Отчеты' },
    ];

    onMounted(async () => {
      try {
        const data = await api.get('/api/app-info');
        botName.value = data.botName;
      } catch (e) {
        botName.value = '?';
      }
    });

    return { botName, menuOpen, navLinks };
  },

  template: `
    <header class="u-clearfix u-header u-header" id="sec-e980">
      <div class="u-clearfix u-sheet u-valign-middle u-sheet-1">
        <nav class="u-menu u-menu-dropdown u-offcanvas u-menu-1"
             :class="{ 'u-menu-open': menuOpen }">

          <div class="menu-collapse" style="font-size:1rem;letter-spacing:0"
               @click="menuOpen = !menuOpen">
            <a class="u-button-style u-nav-link u-text-active-palette-1-base u-text-hover-palette-2-base" href="#">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" style="width:16px;height:16px;">
                <rect y="1" width="16" height="2"></rect>
                <rect y="7" width="16" height="2"></rect>
                <rect y="13" width="16" height="2"></rect>
              </svg>
            </a>
          </div>

          <div class="u-custom-menu u-nav-container">
            <ul class="u-nav u-spacing-2 u-unstyled u-nav-1">
              <li v-for="link in navLinks" :key="link.to" class="u-nav-item">
                <router-link
                  :to="link.to"
                  class="u-active-palette-1-base u-border-active-palette-1-base u-border-hover-palette-1-base u-button-style u-hover-palette-1-light-1 u-nav-link u-text-active-white u-text-grey-90 u-text-hover-white"
                  active-class="u-active-palette-1-base u-text-active-white"
                  style="padding: 10px 20px;"
                >{{ link.label }}</router-link>
              </li>
            </ul>
          </div>

          <div class="u-custom-menu u-nav-container-collapse"
               :style="menuOpen ? 'display:block' : ''">
            <div class="u-black u-container-style u-inner-container-layout u-opacity u-opacity-95 u-sidenav">
              <div class="u-sidenav-overflow">
                <div class="u-menu-close" @click="menuOpen = false"></div>
                <ul class="u-align-center u-nav u-popupmenu-items u-unstyled u-nav-2">
                  <li v-for="link in navLinks" :key="link.to" class="u-nav-item">
                    <router-link :to="link.to" class="u-button-style u-nav-link"
                      style="padding: 10px 20px;" @click="menuOpen = false">
                      {{ link.label }}
                    </router-link>
                  </li>
                </ul>
              </div>
            </div>
            <div class="u-black u-menu-overlay u-opacity u-opacity-70"
                 @click="menuOpen = false"></div>
          </div>
        </nav>

        <h1 class="u-text u-text-1">Рассылки: админка для {{ botName }}</h1>
      </div>
    </header>
  `,
};

// ============================================================
// AppFooter
// ============================================================

const AppFooter = {
  setup() {
    const version = ref('');
    onMounted(async () => {
      try {
        const data = await api.get('/api/app-info');
        version.value = data.version;
      } catch (e) { /* ignore */ }
    });
    return { version };
  },

  template: `
    <footer class="u-align-right u-clearfix u-footer u-grey-80 u-footer" id="sec-f73b">
      <a href="https://github.com/11sanach11/telegram-mailing-helper" class="github-corner">
        <svg width="80" height="80" viewBox="0 0 250 250"
             style="fill:#eee;color:#151513;position:absolute;top:0;border:0;right:0;">
          <path d="M0,0 L115,115 L130,115 L142,142 L250,250 L250,0 Z"></path>
          <path d="M128.3,109.0 C113.8,99.7 119.0,89.6 119.0,89.6 C122.0,82.7 120.5,78.6 120.5,78.6
            C119.2,72.0 123.4,76.3 123.4,76.3 C127.3,80.9 125.5,87.3 125.5,87.3 C122.9,97.6 130.6,101.9 134.4,103.2"
            fill="currentColor" style="transform-origin:130px 106px;" class="octo-arm"></path>
          <path d="M115.0,115.0 C114.9,115.1 118.7,116.5 119.8,115.4 L133.7,101.6 C136.9,99.2 139.9,98.4 142.2,98.6
            C133.8,88.0 127.5,74.4 143.8,58.0 C148.5,53.4 154.0,51.2 159.7,51.0 C160.3,49.4 163.2,43.6 171.4,40.1
            C171.4,40.1 176.1,42.5 178.8,56.2 C183.1,58.6 187.2,61.8 190.9,65.4 C194.5,69.0 197.7,73.2 200.1,77.6
            C213.8,80.2 216.3,84.9 216.3,84.9 C212.7,93.1 206.9,96.0 205.4,96.6 C205.1,102.4 203.0,107.8 198.3,112.5
            C181.9,128.9 168.3,122.5 157.7,114.1 C157.9,116.9 156.7,120.9 152.7,124.9 L141.0,136.5
            C139.8,137.7 141.6,141.9 141.8,141.8 Z"
            fill="currentColor" class="octo-body"></path>
        </svg>
      </a>
      <style>
        .github-corner:hover .octo-arm { animation: octocat-wave 560ms ease-in-out }
        @keyframes octocat-wave {
          0%,100%{ transform:rotate(0) }
          20%,60%{ transform:rotate(-25deg) }
          40%,80%{ transform:rotate(10deg) }
        }
      </style>
      <div class="u-clearfix u-sheet u-sheet-1">
        <div class="u-align-left u-valign-middle">V{{ version }}</div>
      </div>
    </footer>
  `,
};

// ============================================================
// DispatchListsView
// ============================================================

const DispatchListsView = {
  setup() {
    /** @type {import('vue').Ref<GroupNameInfo[]>} */
    const groups = ref([]);
    /** @type {import('vue').Ref<number|null>} */
    const selectedId = ref(null);
    /** @type {import('vue').Ref<GroupDetail|null>} */
    const groupDetail = ref(null);
    const activeTab = ref('current'); // 'current' | 'add'

    const addForm = reactive({
      name: '',
      description: '',
      list: '',
      groupSize: '5',
      repeatTimes: '1',
      disableByDefault: false,
      showCommentWithBlock: false,
    });

    /** @type {import('vue').Ref<string[]>} */
    const existingNames = computed(() => groups.value.map((g) => g.dispatch_group_name));

    const lineCount = computed(() =>
      addForm.list ? addForm.list.split('\n').length : 0
    );

    async function loadGroups() {
      groups.value = await api.get('/api/dispatch-groups');
    }

    /** @param {number} id */
    async function selectGroup(id) {
      selectedId.value = id;
      groupDetail.value = await api.get('/api/dispatch-groups/' + id);
    }

    /**
     * @param {string} field
     * @param {string|number|null} currentValue
     * @param {number} grId
     */
    async function editField(field, currentValue, grId) {
      const { value } = await Swal.fire({
        input: 'textarea',
        inputLabel: 'Укажите новое значение для поля:',
        inputPlaceholder: 'Необходимое вам значение...',
        inputValue: currentValue != null ? String(currentValue) : '',
        showCancelButton: true,
      });
      if (value !== undefined) {
        await api.post('/api/lists/' + grId + '/change', { [field]: value });
        await Promise.all([selectGroup(grId), loadGroups()]);
      }
    }

    /**
     * @param {number} grId
     * @param {'enable'|'disable'} state
     */
    async function changeState(grId, state) {
      await api.post('/api/lists/' + grId + '/state', { state });
      await Promise.all([selectGroup(grId), loadGroups()]);
    }

    /** @param {number} grId */
    async function removeGroup(grId) {
      if (!confirm('Вы уверены что хотите удалить кнопку?')) return;
      await api.post('/api/lists/' + grId + '/change', { hidden: true });
      groupDetail.value = null;
      selectedId.value = null;
      await loadGroups();
    }

    /** @param {Event} event */
    function loadFromFile(event) {
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => { addForm.list = e.target.result; };
      reader.readAsText(file);
    }

    /** @param {string} id - UUID from /api/lists/add response */
    function pollDispatchState(id) {
      return new Promise((resolve) => {
        let interval;
        Swal.fire({
          title: 'Загружаю данные... Подождите...',
          html: 'Начинается загрузка данных, подождите.',
          timer: 30000,
          didOpen: () => {
            Swal.showLoading();
            Swal.stopTimer();
            interval = setInterval(async () => {
              try {
                const data = await api.get('/api/lists/' + id + '/state');
                if (data && data.state) {
                  Swal.getHtmlContainer().textContent = data.text;
                  if (data.state === 'finished') {
                    clearInterval(interval);
                    Swal.hideLoading();
                    Swal.resumeTimer();
                  }
                }
              } catch (e) {
                clearInterval(interval);
                Swal.hideLoading();
                Swal.getHtmlContainer().textContent = 'Ошибка: ' + e.message;
              }
            }, 1000);
          },
          willClose: () => {
            clearInterval(interval);
            resolve();
          },
        }).then(resolve);
      });
    }

    async function submitAddForm() {
      let response;
      try {
        response = await api.post('/api/lists/add', {
          name: addForm.name,
          description: addForm.description,
          list: addForm.list,
          groupSize: addForm.groupSize,
          repeatTimes: addForm.repeatTimes,
          disableByDefault: addForm.disableByDefault,
          showCommentWithBlock: addForm.showCommentWithBlock,
        });
      } catch (e) {
        await Swal.fire('Ошибка', 'Не удалось отправить данные: ' + e.message, 'error');
        return;
      }

      if (!response || !response.success) {
        await Swal.fire('Ошибка', (response && response.text) || 'Что-то пошло не так', 'error');
        return;
      }

      await pollDispatchState(response.id);
      Object.assign(addForm, {
        name: '', description: '', list: '',
        groupSize: '5', repeatTimes: '1',
        disableByDefault: false, showCommentWithBlock: false,
      });
      await loadGroups();
    }

    onMounted(loadGroups);

    return {
      groups, selectedId, groupDetail, activeTab,
      addForm, existingNames, lineCount,
      selectGroup, editField, changeState, removeGroup, loadFromFile, submitAddForm,
    };
  },

  template: `
    <section class="u-align-left u-clearfix u-section-1" id="sec-dedf">
      <div class="u-clearfix u-sheet u-valign-middle u-sheet-1">
        <div class="u-expanded-width u-tab-links-align-left u-tabs u-tabs-1">

          <!-- Tab links -->
          <ul class="u-spacing-30 u-tab-list u-unstyled" role="tablist">
            <li class="u-tab-item" role="presentation">
              <a :class="['u-active-palette-2-base u-button-style u-tab-link u-text-body-color', activeTab === 'current' ? 'active' : '']"
                 href="#" role="tab" @click.prevent="activeTab = 'current'">
                &#128231;&nbsp;Текущие рассылки
              </a>
            </li>
            <li class="u-tab-item" role="presentation">
              <a :class="['u-active-palette-2-base u-button-style u-tab-link u-text-body-color', activeTab === 'add' ? 'active' : '']"
                 href="#" role="tab" @click.prevent="activeTab = 'add'">
                &#128196;&nbsp;Добавить новую
              </a>
            </li>
          </ul>

          <!-- Tab content -->
          <div class="u-tab-content">

            <!-- Current lists tab -->
            <div :class="['u-container-style u-tab-pane', activeTab === 'current' ? 'u-tab-active' : '']"
                 role="tabpanel">
              <div class="u-container-layout u-container-layout-1">
                <div class="u-clearfix u-expanded-width u-gutter-0 u-layout-wrap u-layout-wrap-1">
                  <div class="u-layout">
                    <div class="u-layout-row">

                      <!-- Group buttons -->
                      <div class="u-container-style u-layout-cell u-size-20 u-layout-cell-1">
                        <div class="u-container-layout u-container-layout-2" id="dispatch-group-buttons">
                          <a v-for="g in groups" :key="g.id"
                             style="width:100%"
                             href="#"
                             @click.prevent="selectGroup(g.id)"
                             :class="['u-border-5', g.enabled ? 'u-border-green' : 'u-border-red',
                                      'u-btn u-btn-round u-button-style u-hover-black u-none u-radius-9 u-text-black u-text-hover-white u-btn-1',
                                      selectedId === g.id ? 'u-active' : '']">
                            {{ g.dispatch_group_name }}
                          </a>
                        </div>
                      </div>

                      <!-- Group info -->
                      <div class="u-container-style u-layout-cell u-size-40 u-layout-cell-2">
                        <div class="u-container-layout u-valign-top u-container-layout-3">
                          <div id="dispatch-group-info">
                            <template v-if="!groupDetail">
                              <ul class="u-text u-text-1">
                                <li>Для получения информации, выберите рассылку</li>
                              </ul>
                            </template>
                            <template v-else>
                              <ul class="u-text u-text-1">
                                <li>
                                  Название:
                                  <span>{{ groupDetail.info.dispatch_group_name }}</span>
                                  &rarr; <a href="#" @click.prevent="editField('dispatch_group_name', groupDetail.info.dispatch_group_name, groupDetail.info.id)">Редактировать</a>
                                </li>
                                <li>
                                  Описание:
                                  <span>{{ groupDetail.info.description }}</span>
                                  &rarr; <a href="#" @click.prevent="editField('description', groupDetail.info.description, groupDetail.info.id)">Редактировать</a>
                                </li>
                                <li>
                                  Приоритет (целое число):
                                  <span>{{ groupDetail.info.priority }}</span>
                                  &rarr; <a href="#" @click.prevent="editField('priority', groupDetail.info.priority, groupDetail.info.id)">Редактировать</a>
                                </li>
                                <li>
                                  Выводить описание с каждым блоком (1-выводить, 0-нет):
                                  <span>{{ groupDetail.info.show_comment_with_block }}</span>
                                  &rarr; <a href="#" @click.prevent="editField('show_comment_with_block', groupDetail.info.show_comment_with_block, groupDetail.info.id)">Редактировать</a>
                                </li>
                                <li>
                                  Показывать кол-во взятых блоков (1-выводить, 0-нет):
                                  <span>{{ groupDetail.info.show_count_of_taken_blocks }}</span>
                                  &rarr; <a href="#" @click.prevent="editField('show_count_of_taken_blocks', groupDetail.info.show_count_of_taken_blocks, groupDetail.info.id)">Редактировать</a>
                                </li>
                                <li>
                                  Показывать только для tgId (через запятую, -tgId для исключения):
                                  <span>{{ groupDetail.info.show_group_only_for }}</span>
                                  &rarr; <a href="#" @click.prevent="editField('show_group_only_for', groupDetail.info.show_group_only_for, groupDetail.info.id)">Редактировать</a>
                                </li>
                                <li>Повторно отдавать блок раз: {{ groupDetail.info.repeat }}</li>
                                <li>Количество блоков: {{ groupDetail.info.count }}</li>
                                <li>Кол-во назначенных блоков: {{ groupDetail.info.assigned_count }}</li>
                                <li>Кол-во свободных блоков: {{ groupDetail.info.free_count }}</li>
                              </ul>
                              <a href="#" @click.prevent="changeState(groupDetail.info.id, groupDetail.state.value)">
                                {{ groupDetail.state.text }}
                              </a>
                              <template v-if="!groupDetail.info.enabled">
                                <p></p>
                                <a href="#" style="color:red"
                                   @click.prevent="removeGroup(groupDetail.info.id)">УДАЛИТЬ КНОПКУ</a>
                                <p></p>
                                <a :href="'/api/lists/' + groupDetail.info.id + '/downloadData.txt'"
                                   target="_blank" style="color:green">Скачать неиспользованные блоки</a>
                              </template>
                            </template>
                          </div>
                        </div>
                      </div>

                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Add new tab -->
            <div :class="['u-container-style u-tab-pane', activeTab === 'add' ? 'u-tab-active' : '']"
                 role="tabpanel">
              <div class="u-container-layout u-container-layout-4">
                <div class="u-form u-form-1">
                  <form @submit.prevent="submitAddForm"
                        class="u-clearfix u-form-spacing-10 u-form-vertical u-inner-form"
                        style="padding: 9px;">

                    <div class="u-form-group u-form-name">
                      <datalist id="dispatchGroupNames">
                        <option v-for="n in existingNames" :key="n" :value="n"></option>
                      </datalist>
                      <label class="u-form-control-hidden u-label">Название</label>
                      <input type="text" list="dispatchGroupNames" v-model="addForm.name"
                             placeholder="Название для рассылки (как на кнопке)"
                             class="u-border-1 u-border-grey-30 u-input u-input-rectangle u-radius-5 u-white"
                             required>
                    </div>

                    <div class="u-form-group">
                      <label class="u-form-control-hidden u-label">Описание</label>
                      <input type="text" v-model="addForm.description"
                             placeholder="Описание (устанавливается только для новых кнопок!)"
                             class="u-border-1 u-border-grey-30 u-input u-input-rectangle u-radius-5 u-white">
                    </div>

                    <div class="u-form-group u-form-message">
                      <label class="u-form-control-hidden u-label">Список</label>
                      <textarea v-model="addForm.list" rows="15" cols="50"
                                placeholder="Собственно сам список"
                                class="u-border-1 u-border-grey-30 u-input u-input-rectangle u-radius-5 u-white"
                                required></textarea>
                      <label class="u-label">Количество строк: {{ lineCount }}</label>
                      <br>
                      <input type="button" value="Загрузить из .txt ->"
                             @click="$refs.fileInput.click()">
                      <input ref="fileInput" type="file" accept=".txt"
                             style="display:none" @change="loadFromFile">
                    </div>

                    <div class="u-form-group u-form-select u-form-group-4">
                      <label class="u-label">Разделить список на группы по:</label>
                      <div class="u-form-select-wrapper">
                        <datalist id="groupSizeVariants">
                          <option>4</option><option>5</option><option>9</option>
                        </datalist>
                        <input type="text" v-model="addForm.groupSize" list="groupSizeVariants"
                               class="u-border-1 u-border-grey-30 u-input u-input-rectangle u-radius-5 u-white"
                               required>
                      </div>
                    </div>

                    <div class="u-form-group u-form-select u-form-group-4">
                      <label class="u-label">Выдавать каждый блок следующее число раз
                        (только для новых кнопок, менять после создания невозможно!):</label>
                      <div class="u-form-select-wrapper">
                        <datalist id="repeatTimesVariants">
                          <option>1</option><option>2</option><option>4</option>
                        </datalist>
                        <input type="text" v-model="addForm.repeatTimes" list="repeatTimesVariants"
                               class="u-border-1 u-border-grey-30 u-input u-input-rectangle u-radius-5 u-white"
                               required>
                      </div>
                    </div>

                    <div class="u-form-checkbox u-form-group u-form-group-5">
                      <input type="checkbox" id="checkbox-0931" v-model="addForm.disableByDefault">
                      <label for="checkbox-0931" class="u-label">
                        Скрыть кнопку (только для новых кнопок, для существующих останется как есть!)
                      </label>
                    </div>

                    <div class="u-form-checkbox u-form-group u-form-group-5">
                      <input type="checkbox" id="checkbox-0932" v-model="addForm.showCommentWithBlock">
                      <label for="checkbox-0932" class="u-label">
                        С каждым блоком показывать также и описание
                        (только для новых кнопок, для существующих останется как есть!)
                      </label>
                    </div>

                    <div class="u-align-left u-form-group u-form-submit">
                      <button type="submit" class="u-btn u-btn-submit u-button-style">Добавить</button>
                    </div>

                  </form>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </section>
  `,
};

// ============================================================
// UsersView
// ============================================================

const UsersView = {
  setup() {
    /** @type {import('vue').Ref<UserItem[]>} */
    const users = ref([]);
    const loading = ref(true);

    async function loadUsers() {
      loading.value = true;
      users.value = await api.get('/api/users-list');
      loading.value = false;
    }

    /** @param {number} userId */
    async function changeUserState(userId) {
      const data = await api.post('/api/users/state/change', { id: userId });
      const user = users.value.find((u) => u.id === userId);
      if (user && data) {
        user.state = data.state;
        user.localizedState = data.localizedState;
      }
    }

    onMounted(loadUsers);

    return { users, loading, changeUserState };
  },

  template: `
    <section class="u-align-center u-clearfix u-section-1" id="sec-2267">
      <div class="u-clearfix u-sheet u-valign-top u-sheet-1">
        <div v-if="loading" style="padding:20px">Загрузка...</div>
        <div v-else class="u-expanded-width u-table u-table-responsive u-table-1">
          <table class="u-table-entity u-table-entity-1">
            <colgroup>
              <col width="5%"><col width="19%"><col width="19%">
              <col width="19%"><col width="19%"><col width="19%">
            </colgroup>
            <thead class="u-black u-table-header u-table-header-1">
              <tr style="height:21px">
                <th class="u-border-1 u-border-black u-table-cell">#ID</th>
                <th class="u-border-1 u-border-black u-table-cell">TgId</th>
                <th class="u-border-1 u-border-black u-table-cell">Пользователь</th>
                <th class="u-border-1 u-border-black u-table-cell">Состояние</th>
                <th class="u-border-1 u-border-black u-table-cell">Действия</th>
                <th class="u-border-1 u-border-black u-table-cell">Добавлен</th>
              </tr>
            </thead>
            <tbody class="u-table-alt-grey-5 u-table-body">
              <tr v-for="user in users" :key="user.id" style="height:21px">
                <td class="u-border-1 u-border-grey-30 u-first-column u-grey-50 u-table-cell">{{ user.id }}</td>
                <td class="u-border-1 u-border-grey-30 u-table-cell">{{ user.telegram_id }}</td>
                <td class="u-border-1 u-border-grey-30 u-table-cell">{{ user.name }}</td>
                <td class="u-border-1 u-border-grey-30 u-table-cell">{{ user.localizedState }}</td>
                <td class="u-border-1 u-border-active-palette-2-base u-border-hover-palette-1-base u-btn-rectangle u-none u-table-cell u-text-palette-1-base">
                  <a href="#" @click.prevent="changeUserState(user.id)"
                     class="u-active-none u-border-none u-btn u-button-link u-button-style u-hover-none u-none u-text-palette-1-base">
                    Изменить состояние
                  </a>
                </td>
                <td class="u-border-1 u-border-grey-30 u-table-cell">{{ user.created }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `,
};

// ============================================================
// SettingsView
// ============================================================

const SettingsView = {
  setup() {
    /** @type {import('vue').Ref<StorageItem[]>} */
    const settings = ref([]);
    const loading = ref(true);

    async function loadSettings() {
      loading.value = true;
      settings.value = await api.get('/api/settings-list');
      loading.value = false;
    }

    /** @param {StorageItem} setting */
    async function editSetting(setting) {
      const { value } = await Swal.fire({
        input: 'textarea',
        inputLabel: 'Укажите новое значение для свойства: ' + setting.key,
        inputPlaceholder: 'Необходимое вам значение...',
        inputValue: setting.value,
        showCancelButton: true,
      });
      if (value !== undefined) {
        const data = await api.post('/api/settings/change', { key: setting.key, value });
        if (data && data.success) {
          setting.value = data.value;
        }
      }
    }

    onMounted(loadSettings);

    return { settings, loading, editSetting };
  },

  template: `
    <section class="u-align-center u-clearfix u-section-1" id="sec-2267">
      <div class="u-clearfix u-sheet u-valign-top u-sheet-1">
        <div v-if="loading" style="padding:20px">Загрузка...</div>
        <div v-else class="u-expanded-width u-table u-table-responsive u-table-1">
          <table class="u-table-entity u-table-entity-1">
            <colgroup>
              <col width="20%"><col width="40%"><col width="40%">
            </colgroup>
            <thead class="u-black u-table-header u-table-header-1">
              <tr style="height:21px">
                <th class="u-border-1 u-border-black u-table-cell">Ключ</th>
                <th class="u-border-1 u-border-black u-table-cell">Описание</th>
                <th class="u-border-1 u-border-black u-table-cell">Значение</th>
              </tr>
            </thead>
            <tbody class="u-table-alt-grey-5 u-table-body">
              <tr v-for="s in settings" :key="s.key" style="height:21px">
                <td class="u-border-1 u-border-grey-30 u-first-column u-table-cell">
                  <a href="#" @click.prevent="editSetting(s)">{{ s.key }}</a>
                </td>
                <td class="u-border-1 u-border-grey-30 u-table-cell">{{ s.description }}</td>
                <td class="u-border-1 u-border-grey-30 u-table-cell">{{ s.value }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `,
};

// ============================================================
// ReportsView
// ============================================================

const ReportsView = {
  setup() {
    /** @type {import('vue').Ref<ReportItem[]>} */
    const reports = ref([]);
    const activeTab = ref('');
    const loading = ref(true);

    onMounted(async () => {
      loading.value = true;
      reports.value = await api.get('/api/reports');
      if (reports.value.length > 0) {
        activeTab.value = reports.value[0].key;
      }
      loading.value = false;
    });

    return { reports, activeTab, loading };
  },

  template: `
    <section class="u-align-left u-clearfix u-section-2" id="sec-f619">
      <div class="u-clearfix u-sheet u-sheet-1">
        <div v-if="loading" style="padding:20px">Загрузка отчетов...</div>
        <div v-else class="u-expanded-width u-tab-links-align-left u-tabs u-tabs-1">
          <ul class="u-spacing-5 u-tab-list u-unstyled" role="tablist">
            <li v-for="r in reports" :key="r.key" class="u-tab-item" role="presentation">
              <a :class="['u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white',
                          activeTab === r.key ? 'active' : '']"
                 href="#" role="tab" @click.prevent="activeTab = r.key">
                {{ r.title }}
              </a>
            </li>
          </ul>
          <div class="u-tab-content">
            <div v-for="r in reports" :key="r.key"
                 :class="['u-container-style u-tab-pane', activeTab === r.key ? 'u-tab-active' : '']"
                 role="tabpanel">
              <div class="u-container-layout u-container-layout-1">
                <div class="u-container-style u-group u-white u-group-1">
                  <div class="u-container-layout u-container-layout-2">
                    <pre>{{ r.data }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `,
};

// ============================================================
// Router
// ============================================================

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dispatch_lists' },
    { path: '/dispatch_lists', component: DispatchListsView },
    { path: '/users', component: UsersView },
    { path: '/settings', component: SettingsView },
    { path: '/reports', component: ReportsView },
  ],
});

// ============================================================
// App bootstrap
// ============================================================

const vueApp = createApp({
  template: `
    <app-header></app-header>
    <router-view></router-view>
    <app-footer></app-footer>
  `,
});

vueApp.use(router);
vueApp.component('app-header', AppHeader);
vueApp.component('app-footer', AppFooter);

// Mount on a simpler container (avoid nesting with index.html's #app components)
const mountEl = document.getElementById('app');
// Clear placeholder children so Vue takes full control
mountEl.innerHTML = '';
vueApp.mount(mountEl);
