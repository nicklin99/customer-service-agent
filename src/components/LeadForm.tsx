import { useState, useEffect } from 'react'
import type { LeadData } from '../api'
import { getLeads } from '../api'
import { useBrand } from '../context/BrandContext'

interface Props {
  leadData: LeadData | null
  onUpdate: (data: LeadData) => void
}

export default function LeadForm({ leadData, onUpdate }: Props) {
  const brand = useBrand()

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
  const [allLeads, setAllLeads] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (leadData) {
      setLocalLead(leadData)
    }
  }, [leadData])

  useEffect(() => {
    loadLeads()
  }, [])

  const loadLeads = async () => {
    setLoading(true)
    try {
      const leads = await getLeads()
      setAllLeads(leads)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (field: keyof LeadData, value: string) => {
    const updated = { ...localLead, [field]: value }
    setLocalLead(updated)
    onUpdate(updated)
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
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* 左侧：线索表单 */}
      <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">📋 客户线索</h2>
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

        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-500">
            💡 提示：客户与{brand.agentName}对话过程中，AI 会自动识别潜在客户并收集以上信息。
            您也可以手动填写或编辑。
          </p>
        </div>
      </div>

      {/* 右侧：历史线索列表 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">📝 历史线索</h2>

        {loading ? (
          <div className="text-sm text-gray-400 text-center py-8">加载中...</div>
        ) : allLeads.length === 0 ? (
          <div className="text-sm text-gray-400 text-center py-8">
            暂无历史线索
            <br />
            <span className="text-xs">对话中收集的线索会出现在这里</span>
          </div>
        ) : (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {allLeads.map((item, i) => (
              <div
                key={item.conversation_id || i}
                className="p-3 border border-gray-100 rounded-lg hover:border-gold/30 transition-colors cursor-pointer"
              >
                <div className="text-sm font-medium text-gray-800">
                  {item.lead?.name || '未知'}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {item.lead?.company || '未填公司'} · {item.lead?.needs?.slice(0, 30) || '暂无需求'}
                </div>
                <div className="text-[10px] text-gray-400 mt-1">
                  {item.updated_at || ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
