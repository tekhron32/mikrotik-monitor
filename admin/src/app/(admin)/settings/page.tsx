import { ChangePasswordForm } from '@/components/settings/change-password-form'

export default function SettingsPage() {
  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-white">Настройки</h1>
        <p className="text-sm text-slate-500 mt-1">Управление аккаунтом Super Admin</p>
      </div>

      <div className="space-y-6">
        {/* Смена пароля */}
        <div className="border border-[#1e2535] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1e2535] bg-[#0d1018]">
            <h2 className="text-sm font-medium text-slate-200">Смена пароля</h2>
          </div>
          <div className="p-4">
            <ChangePasswordForm />
          </div>
        </div>

        {/* Смена через терминал */}
        <div className="border border-[#1e2535] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1e2535] bg-[#0d1018]">
            <h2 className="text-sm font-medium text-slate-200">Смена пароля через терминал</h2>
          </div>
          <div className="p-4 space-y-3">
            <p className="text-xs text-slate-500">Если нет доступа к панели — используй команды на сервере:</p>
            <div className="bg-[#0d1018] border border-[#1e2535] rounded-lg p-3 font-mono text-xs text-slate-300 space-y-1">
              <p className="text-slate-500"># 1. Генерируем хеш нового пароля</p>
              <p>python3 -c "import bcrypt; print(bcrypt.hashpw(b'НовыйПароль', bcrypt.gensalt(12)).decode())"</p>
              <p className="text-slate-500 mt-2"># 2. Обновляем в БД</p>
              <p>docker exec nebulanet-postgres psql -U nebulanet -d nebulanet_v2 \</p>
              <p className="pl-4">-c "UPDATE super_admins SET password='ХЕШ' WHERE email='admin@nebulanet.local';"</p>
            </div>
            <p className="text-xs text-slate-500">Сервер: <span className="text-slate-300 font-mono">192.168.1.53</span> · user: <span className="text-slate-300 font-mono">tehron</span></p>
          </div>
        </div>

        {/* Информация об аккаунте */}
        <div className="border border-[#1e2535] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1e2535] bg-[#0d1018]">
            <h2 className="text-sm font-medium text-slate-200">Информация</h2>
          </div>
          <div className="p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Email</span>
              <span className="text-slate-300 font-mono">admin@nebulanet.local</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Роль</span>
              <span className="text-blue-400">Super Admin</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Портал v2.0</span>
              <span className="text-slate-300 font-mono">192.168.1.53:3001</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Мониторинг v1.0</span>
              <span className="text-slate-300 font-mono">192.168.1.53:8000</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
