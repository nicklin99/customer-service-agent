import type { LeadData, ProfileData } from '../api'

interface Props {
  profileData: ProfileData | null
  leadData: LeadData | null
  conversationId: string
  onRefresh: () => void
}

const LEVEL_COLORS: Record<string, string> = {
  '高': 'bg-red-50 text-red-700 border-red-200',
  '中': 'bg-orange-50 text-orange-700 border-orange-200',
  '低': 'bg-blue-50 text-blue-700 border-blue-200',
  '未知': 'bg-gray-50 text-gray-500 border-gray-200',
}

const URGENCY_COLORS: Record<string, string> = {
  '紧急': 'bg-red-50 text-red-700 border-red-200',
  '一般': 'bg-yellow-50 text-yellow-700 border-yellow-200',
  '不急': 'bg-green-50 text-green-700 border-green-200',
  '未知': 'bg-gray-50 text-gray-500 border-gray-200',
}

export default function ProfilePanel({ profileData, leadData, conversationId, onRefresh }: Props) {
  const profile = profileData

  if (!profile && !leadData) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
        <div className="text-4xl mb-4">📊</div>
        <h3 className="text-lg font-semibold text-gray-700 mb-2">暂无用户画像</h3>
        <p className="text-sm text-gray-500 mb-4">
          与小星对话过程中，AI 会自动分析客户特征并生成画像。
          <br />
          请先完成一轮对话，收集到基础线索后画像将自动生成。
        </p>
        <button
          onClick={onRefresh}
          className="px-4 py-2 text-sm text-gold border border-gold rounded-lg hover:bg-gold/5 transition-colors"
        >
          刷新数据
        </button>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* 画像概览 */}
      <div className="lg:col-span-2 space-y-6">
        {/* 头部卡片 */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">📊 用户画像分析</h2>
            <button
              onClick={onRefresh}
              className="text-xs text-gold hover:text-gold-dark transition-colors"
            >
              刷新
            </button>
          </div>

          {profile ? (
            <div className="space-y-4">
              {/* 标签行 */}
              <div className="flex flex-wrap gap-2">
                <span
                  className={`px-3 py-1 text-xs font-medium rounded-full border ${
                    LEVEL_COLORS[profile.intent_level] || LEVEL_COLORS['未知']
                  }`}
                >
                  意向: {profile.intent_level}
                </span>
                <span
                  className={`px-3 py-1 text-xs font-medium rounded-full border ${
                    URGENCY_COLORS[profile.urgency] || URGENCY_COLORS['未知']
                  }`}
                >
                  紧急度: {profile.urgency}
                </span>
                <span className="px-3 py-1 text-xs font-medium text-gray-600 bg-gray-50 rounded-full border border-gray-200">
                  {profile.customer_type || '未知类型'}
                </span>
                <span className="px-3 py-1 text-xs font-medium text-gray-600 bg-gray-50 rounded-full border border-gray-200">
                  预估: {profile.estimated_value || '未知'}
                </span>
              </div>

              {/* 核心需求 */}
              <div className="p-4 bg-gold/5 border border-gold/20 rounded-lg">
                <div className="text-xs text-gray-500 mb-1">核心需求</div>
                <div className="text-sm font-medium text-gray-800">
                  {profile.primary_need || '待分析'}
                </div>
              </div>

              {/* 画像总结 */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="text-xs text-gray-500 mb-1">画像总结</div>
                <div className="text-sm text-gray-700">{profile.persona_summary || '待分析'}</div>
              </div>

              {/* 痛点 */}
              {profile.pain_points && profile.pain_points.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-2">客户痛点</div>
                  <div className="space-y-2">
                    {profile.pain_points.map((point, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <span className="text-red-400 mt-0.5">•</span>
                        <span className="text-sm text-gray-700">{point}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 关键洞察 */}
              {profile.key_insights && profile.key_insights.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-2">关键洞察</div>
                  <div className="space-y-2">
                    {profile.key_insights.map((insight, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <span className="text-gold mt-0.5">✦</span>
                        <span className="text-sm text-gray-700">{insight}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-400 text-center py-8">
              画像分析尚未完成，请继续与小星对话
            </div>
          )}
        </div>

        {/* 推荐服务 */}
        {profile?.recommended_services && profile.recommended_services.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">🎯 推荐服务</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {profile.recommended_services.map((service, i) => (
                <div
                  key={i}
                  className="p-3 border border-gold/30 bg-gold/5 rounded-lg text-sm text-gray-700"
                >
                  {service}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 右侧：线索摘要 */}
      <div className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">👤 客户信息</h3>
          {leadData ? (
            <dl className="space-y-3">
              {[
                ['姓名', leadData.name],
                ['电话', leadData.phone],
                ['邮箱', leadData.email],
                ['公司', leadData.company],
                ['职位', leadData.position],
                ['预算', leadData.budget],
                ['时间线', leadData.timeline],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between">
                  <dt className="text-xs text-gray-500">{label}</dt>
                  <dd className="text-xs text-gray-800 font-medium text-right max-w-[60%] truncate">
                    {value || '—'}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <div className="text-xs text-gray-400 text-center py-4">
              暂无线索数据
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">📈 会话信息</h3>
          <div className="text-xs text-gray-500 space-y-2">
            <div className="flex justify-between">
              <span>会话 ID</span>
              <span className="font-mono text-gray-700">{conversationId.slice(0, 16)}...</span>
            </div>
          </div>
        </div>

        <div className="p-4 bg-primary rounded-xl text-white text-xs">
          <p className="opacity-80 mb-2">
            💡 画像分析会随着对话深入不断完善。
          </p>
          <p className="opacity-60">
            建议引导客户多描述具体需求和场景，AI 将获得更精准的分析结果。
          </p>
        </div>
      </div>
    </div>
  )
}
