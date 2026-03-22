'use strict';

// ── API helper ─────────────────────────────────────────────────────────────

const BASE_URL = '';

async function apiCall(method, path, body) {
  const token = localStorage.getItem('pwa_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const opts = { method, headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const resp = await fetch(BASE_URL + path, opts);
  if (resp.status === 401) {
    localStorage.removeItem('pwa_token');
    router.push('/login');
    throw new Error('Unauthorized');
  }
  if (!resp.ok) {
    let detail = 'Ошибка сервера';
    try { detail = (await resp.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

const api = {
  get: (path) => apiCall('GET', path),
  post: (path, body) => apiCall('POST', path, body),
  delete: (path, body) => apiCall('DELETE', path, body),
};

// ── Local message history (last 10) ────────────────────────────────────────

const HISTORY_KEY = 'pwa_message_history';

function getHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); }
  catch { return []; }
}

function addToHistory(entry) {
  const history = getHistory();
  history.unshift({ ...entry, time: new Date().toLocaleTimeString() });
  if (history.length > 10) history.length = 10;
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

// ── Push subscription helpers ───────────────────────────────────────────────

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

async function subscribeToPush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return null;
  const { publicKey } = await api.get('/api/pwa/push/vapid-public-key');
  if (!publicKey) return null;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });
  const subJson = sub.toJSON();
  await api.post('/api/pwa/push/subscribe', {
    endpoint: subJson.endpoint,
    keys: subJson.keys,
  });
  return sub;
}

async function unsubscribeFromPush() {
  if (!('serviceWorker' in navigator)) return;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return;
  await api.delete('/api/pwa/push/unsubscribe', { endpoint: sub.endpoint });
  await sub.unsubscribe();
}

async function getPushSubscription() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

// ── Vue components ──────────────────────────────────────────────────────────

const LoginView = {
  template: `
    <div class="container" style="padding-top:40px">
      <div class="card">
        <h2 style="margin-bottom:16px;font-size:20px">Вход</h2>
        <div v-if="error" class="alert alert-error">{{ error }}</div>
        <div class="form-group">
          <label>Email</label>
          <input type="email" v-model="email" placeholder="your@email.com" @keyup.enter="submit">
        </div>
        <div class="form-group">
          <label>Пароль</label>
          <input type="password" v-model="password" placeholder="••••••••" @keyup.enter="submit">
        </div>
        <button class="btn btn-primary" @click="submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span v-else>Войти</span>
        </button>
        <p style="margin-top:14px;text-align:center;font-size:14px">
          Нет аккаунта? <a href="#/register">Зарегистрироваться</a>
        </p>
      </div>
    </div>`,
  data() { return { email: '', password: '', error: '', loading: false }; },
  methods: {
    async submit() {
      this.error = '';
      if (!this.email || !this.password) { this.error = 'Введите email и пароль'; return; }
      this.loading = true;
      try {
        const { access_token } = await api.post('/api/pwa/auth/login', {
          email: this.email, password: this.password });
        localStorage.setItem('pwa_token', access_token);
        this.$router.push('/');
      } catch (e) { this.error = e.message; }
      this.loading = false;
    }
  }
};

const RegisterView = {
  template: `
    <div class="container" style="padding-top:40px">
      <div class="card">
        <h2 style="margin-bottom:16px;font-size:20px">Регистрация</h2>
        <div v-if="error" class="alert alert-error">{{ error }}</div>
        <div v-if="success" class="alert alert-success">{{ success }}</div>
        <div class="form-group">
          <label>Имя</label>
          <input type="text" v-model="name" placeholder="Ваше имя">
        </div>
        <div class="form-group">
          <label>Email</label>
          <input type="email" v-model="email" placeholder="your@email.com">
        </div>
        <div class="form-group">
          <label>Пароль</label>
          <input type="password" v-model="password" placeholder="Минимум 6 символов">
        </div>
        <button class="btn btn-primary" @click="submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span v-else>Создать аккаунт</span>
        </button>
        <p style="margin-top:14px;text-align:center;font-size:14px">
          Уже есть аккаунт? <a href="#/login">Войти</a>
        </p>
      </div>
    </div>`,
  data() { return { name: '', email: '', password: '', error: '', success: '', loading: false }; },
  methods: {
    async submit() {
      this.error = ''; this.success = '';
      if (!this.name || !this.email || !this.password) { this.error = 'Заполните все поля'; return; }
      if (this.password.length < 6) { this.error = 'Пароль должен быть не менее 6 символов'; return; }
      this.loading = true;
      try {
        const { access_token } = await api.post('/api/pwa/auth/register', {
          name: this.name, email: this.email, password: this.password });
        localStorage.setItem('pwa_token', access_token);
        this.$router.push('/');
      } catch (e) { this.error = e.message; }
      this.loading = false;
    }
  }
};

const HomeView = {
  template: `
    <div class="container" style="padding-top:16px">
      <div v-if="user && user.state !== 'confirmed'" class="card">
        <div class="alert alert-info" style="margin-bottom:0">
          <b>Ваш аккаунт ожидает подтверждения администратором.</b><br>
          После подтверждения вы сможете получать блоки рассылок.
        </div>
      </div>
      <div v-if="user && user.state === 'confirmed'">
        <div class="card" v-if="!groups.length && !loading">
          <p style="color:#888;text-align:center">Нет доступных списков рассылок</p>
        </div>
        <div class="card" v-if="loading" style="text-align:center">
          <span class="spinner"></span>
        </div>
        <div class="card" v-for="g in groups" :key="g.id">
          <div class="group-item">
            <div>
              <div class="group-name">{{ g.name }}</div>
              <div class="group-desc" v-if="g.description">{{ g.description }}</div>
            </div>
            <button class="btn btn-primary" style="width:auto;padding:8px 16px"
                    @click="$router.push('/groups/' + g.id + '?name=' + encodeURIComponent(g.name))">
              Получить
            </button>
          </div>
        </div>
      </div>
      <div class="card" v-if="history.length">
        <h3 style="font-size:15px;margin-bottom:8px;color:#666">История (последние 10)</h3>
        <div class="history-item" v-for="(h, i) in history" :key="i">
          <div class="history-time">{{ h.time }}</div>
          <div>{{ h.text }}</div>
        </div>
      </div>
    </div>`,
  data() { return { user: null, groups: [], loading: true, history: [] }; },
  async mounted() {
    this.history = getHistory();
    try {
      this.user = await api.get('/api/pwa/auth/me');
      if (this.user.state === 'confirmed') {
        this.groups = await api.get('/api/pwa/user/groups');
      }
    } catch {}
    this.loading = false;
  }
};

const BlockView = {
  template: `
    <div class="container" style="padding-top:16px">
      <div class="card">
        <h2 style="font-size:17px;margin-bottom:12px">{{ groupName }}</h2>
        <div v-if="error" class="alert alert-error">{{ error }}</div>
        <div v-if="block">
          <div class="block-content">{{ block }}</div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-danger" style="flex:1" @click="returnBlock" :disabled="returning">
              <span v-if="returning" class="spinner"></span>
              <span v-else>↩ Вернуть блок</span>
            </button>
            <button class="btn btn-primary" style="flex:1" @click="getBlock" :disabled="loading">
              <span v-if="loading" class="spinner"></span>
              <span v-else>→ Следующий</span>
            </button>
          </div>
        </div>
        <div v-else-if="loading" style="text-align:center"><span class="spinner"></span></div>
        <div v-else>
          <button class="btn btn-primary" @click="getBlock" :disabled="loading">
            Получить блок
          </button>
        </div>
        <div style="margin-top:12px">
          <a href="#/" style="font-size:14px;color:#c84771">← Назад к спискам</a>
        </div>
      </div>
    </div>`,
  data() { return { groupId: null, groupName: '', block: null, dispatchListId: null,
                    loading: false, returning: false, error: '' }; },
  created() {
    this.groupId = parseInt(this.$route.params.id);
    this.groupName = this.$route.query.name || 'Список';
  },
  methods: {
    async getBlock() {
      this.error = ''; this.loading = true;
      try {
        const res = await api.post(`/api/pwa/user/groups/${this.groupId}/assign`);
        this.block = res.block;
        this.dispatchListId = res.dispatch_list_id;
        if (this.dispatchListId) {
          addToHistory({ text: `[${this.groupName}] Получен блок` });
        }
      } catch (e) { this.error = e.message; }
      this.loading = false;
    },
    async returnBlock() {
      if (!this.dispatchListId) return;
      this.returning = true;
      try {
        await api.post(`/api/pwa/user/groups/${this.groupId}/return/${this.dispatchListId}`);
        addToHistory({ text: `[${this.groupName}] Блок возвращён` });
        this.block = null;
        this.dispatchListId = null;
      } catch (e) { this.error = e.message; }
      this.returning = false;
    }
  }
};

const ProfileView = {
  template: `
    <div class="container" style="padding-top:16px">
      <div class="card" v-if="user">
        <h2 style="font-size:17px;margin-bottom:12px">Профиль</h2>
        <p><b>Имя:</b> {{ user.name }}</p>
        <p><b>Email:</b> {{ user.email }}</p>
        <p><b>Статус:</b>
          <span class="badge" :class="'badge-' + user.state">{{ stateLabel }}</span>
        </p>
        <p><b>Telegram:</b> {{ user.has_telegram ? 'Привязан' : 'Не привязан' }}</p>
      </div>

      <div class="card" v-if="user && !user.has_telegram">
        <h3 style="font-size:15px;margin-bottom:8px">Привязать Telegram</h3>
        <p style="font-size:13px;color:#666;margin-bottom:10px">
          Привязка позволяет использовать бот и приложение как единый аккаунт.
        </p>
        <button class="btn btn-primary" @click="generateToken" :disabled="tokenLoading">
          <span v-if="tokenLoading" class="spinner"></span>
          <span v-else>Сгенерировать код</span>
        </button>
        <div v-if="linkToken" style="margin-top:12px">
          <div class="token-box">{{ linkToken }}</div>
          <p style="font-size:13px;color:#666;margin-top:8px;text-align:center">
            Отправьте боту: <b>/link {{ linkToken }}</b><br>
            Код действителен 10 минут
          </p>
        </div>
        <div v-if="tokenError" class="alert alert-error" style="margin-top:8px">{{ tokenError }}</div>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">Push-уведомления</h3>
        <div class="push-toggle">
          <label class="switch">
            <input type="checkbox" v-model="pushEnabled" @change="togglePush">
            <span class="slider"></span>
          </label>
          <span style="font-size:14px">{{ pushEnabled ? 'Включены' : 'Отключены' }}</span>
        </div>
        <p v-if="pushError" class="alert alert-error" style="margin-top:8px">{{ pushError }}</p>
        <p style="font-size:12px;color:#aaa;margin-top:6px">
          Safari 16.4+ на iOS поддерживается. Firefox и Chrome поддерживаются.
        </p>
      </div>
    </div>`,
  data() { return { user: null, linkToken: '', tokenLoading: false, tokenError: '',
                    pushEnabled: false, pushError: '' }; },
  computed: {
    stateLabel() {
      return { new: 'Новый', confirmed: 'Подтверждён', blocked: 'Заблокирован' }[this.user?.state] || '';
    }
  },
  async mounted() {
    try { this.user = await api.get('/api/pwa/auth/me'); } catch {}
    const sub = await getPushSubscription();
    this.pushEnabled = !!sub;
  },
  methods: {
    async generateToken() {
      this.tokenError = ''; this.tokenLoading = true;
      try {
        const res = await api.post('/api/pwa/auth/telegram-link/generate');
        this.linkToken = res.token;
      } catch (e) { this.tokenError = e.message; }
      this.tokenLoading = false;
    },
    async togglePush() {
      this.pushError = '';
      if (this.pushEnabled) {
        try {
          const perm = await Notification.requestPermission();
          if (perm !== 'granted') { this.pushEnabled = false; this.pushError = 'Разрешение отклонено'; return; }
          await subscribeToPush();
        } catch (e) { this.pushEnabled = false; this.pushError = e.message; }
      } else {
        try { await unsubscribeFromPush(); }
        catch (e) { this.pushEnabled = true; this.pushError = e.message; }
      }
    }
  }
};

// ── Router & App ────────────────────────────────────────────────────────────

const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/register', component: RegisterView, meta: { public: true } },
  { path: '/', component: HomeView },
  { path: '/groups/:id', component: BlockView },
  { path: '/profile', component: ProfileView },
];

const router = VueRouter.createRouter({
  history: VueRouter.createWebHashHistory(),
  routes,
});

router.beforeEach((to) => {
  const token = localStorage.getItem('pwa_token');
  if (!to.meta.public && !token) return '/login';
});

const app = Vue.createApp({
  data() { return {}; },
  computed: {
    isLoggedIn() { return !!localStorage.getItem('pwa_token'); }
  },
  methods: {
    logout() {
      localStorage.removeItem('pwa_token');
      this.$router.push('/login');
    }
  }
});

app.use(router);
app.mount('#app');
