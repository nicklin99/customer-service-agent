import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { fetchBrandConfig, defaultBrand, type BrandConfig } from '../config/brand'

const BrandContext = createContext<BrandConfig>(defaultBrand)

export function BrandProvider({ children }: { children: ReactNode }) {
  const [brand, setBrand] = useState<BrandConfig>(defaultBrand)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchBrandConfig().then((config) => {
      setBrand(config)
      // 同步更新页面标题
      document.title = config.brandTitle
      setLoading(false)
    })
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-sm text-gray-400">加载中...</div>
      </div>
    )
  }

  return <BrandContext.Provider value={brand}>{children}</BrandContext.Provider>
}

export function useBrand(): BrandConfig {
  return useContext(BrandContext)
}
