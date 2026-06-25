import { useState, useEffect } from 'react'
import type { LeadData } from '../api'
import { getLead, saveLead } from '../api'
import { useBrand } from '../context/BrandContext'

interface Props {
  threadId: string
  leadData: LeadData | null
  onUpdate: (data: LeadData) => void
}

export default function LeadForm({ threadId, leadData, onUpdate }: Props) {
  const brand = useBrand()
  const [saving, setSaving] = useState(false)

  const EMPTY_LEAD: LeadData = {
    name: '',
    phone: '',
    email: '',
    company: '',
    position: '',
    needs: '',
    source: brand.defaultSource,
    budget: '',
    timeline: '',
  }
  const [localLead, setLocalLead] = useState<LeadData>(leadData || { ...EMPTY_LEAD })

  useEffect(() => {
    if (leadData) {
      setLocalLead(leadData)
    }
  }, [leadData])

  const handleChange = (field: keyof LeadData, value: string) => {
    const updated = { ...localLead, [field]: value }
    setLocalLead(updated)
    onUpdate(updated)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveLead(threadId, localLead)
    } catch {
      // ignore
    } finally {
      setSaving(false)
    }
  }

  const leadComplete =
    localLead.name && localLead.phone && localLead.email && localLead.needs

  const fields: { key: keyof LeadData; label: string; required: boolean; placeholder: string }[] = [
    { key: 'name', label: '姓名', required: true, placeholder: '客户姓名' },
    { key: 'phone', label: '电话', required: true, placeholder: '手机号码' },
    { key: 'email', label: '邮箱', required: true, placeholder: '电子邮箱' },
    { key: 'company', label: '公司', required: false, placeholder: '公司名称' },
    { key: 'position', label: '职位', required: false, placeholder: '职务' },
    { key: 'needs', label: '需求描述', required: true, placeholder: '请描述客户的需求' },
    { key: 'budget', label: '预算', required: false, placeholder: '预算范围' },
    { key: 'timeline', label: '时间线', required: false, placeholder: '预期启动时间' },
  ]

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 px-4 pb-4">
      {/* 线索表单 */}
      <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">📋 客户线索</h2>
          <div className="flex items-center gap-3">
            {leadComplete ? (
              <span className="px-2 py-1 text-xs font-medium text-green-700 bg-green-50 rounded-full border border-green-200">
                ✓ 信息完整
              </span>
            ) : (
              <span className="px-2 py-1 text-xs font-medium text-orange-700 bg-orange-50 rounded-full border border-orange-200">
                待补充
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {fields.map(({ key, label, required, placeholder }) => (
            <div key={key} className={key === 'needs' ? 'md:col-span-2' : ''}>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                {label}
                {required && <span className="text-red-400 ml-1">*</span>}
              </label>
              {key === 'needs' ? (
                <textarea
                  value={localLead[key]}
                  onChange={(e) => handleChange(key, e.target.value)}
                  placeholder={placeholder}
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-gold focus:border-gold resize-none"
                />
              ) : (
                <input
                  type="text"
                  value={localLead[key]}
                  onChange={(e) => handleChange(key, e.target.value)}
                  placeholder={placeholder}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-gold focus:border-gold"
                />
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 flex items-center justify-between">
          <p className="text-xs text-gray-500">
            💡 数据保存后可在下次打开时自动恢复
          </p>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-1.5 text-xs font-medium text-white bg-primary rounded-lg hover:bg-primary-light disabled:opacity-40 transition-all"
          >
            {saving ? '保存中...' : '保存线索'}
          </button>
        </div>
      </div>

      {/* 右侧：当前线索摘要 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">📋 当前线索</h2>
        {localLead.name ? (
          <div className="space-y-3">
            <div>
              <div className="text-sm font-medium text-gray-800">{localLead.name}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                {localLead.company || '未填公司'}
                {localLead.position ? ` · ${localLead.position}` : ''}
              </div>
            </div>
            {localLead.phone && (
              <div className="text-xs text-gray-500">📞 {localLead.phone}</div>
            )}
            {localLead.email && (
              <div className="text-xs text-gray-500">✉️ {localLead.email}</div>
            )}
            {localLead.needs && (
              <div className="text-xs text-gray-500">
                📝 {localLead.needs.slice(0, 60)}{localLead.needs.length > 60 ? '...' : ''}
              </div>
            )}
            {localLead.updated_at && (
              <div className="text-[10px] text-gray-400 pt-2 border-t border-gray-100">
                上次更新：{new Date(localLead.updated_at).toLocaleString('zh-CN')}
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-gray-400 text-center py-8">
            暂无线索信息
            <br />
            <span className="text-xs">填写表单后保存</span>
          </div>
        )}
      </div>
    </div>
  )
}
