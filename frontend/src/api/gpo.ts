import request from '@/utils/request'

export interface Gpo {
  guid: string
  display_name: string
  when_changed: string
  description: string
}

export interface GpoLink {
  guid: string
  dn: string
  disabled: boolean
  enforced: boolean
}

export interface OuGplinks {
  gplink: string
  gpoptions: number
  block_inheritance: boolean
  links: GpoLink[]
}

export interface SetGplinksPayload {
  links: { guid: string; disabled: boolean; enforced: boolean }[]
  block_inheritance: boolean
}

export const listGpos = (domainId: number) =>
  request.get<Gpo[]>(`/gpo/domains/${domainId}/gpos`)
export const getOuGplinks = (dnB64: string, domainId: number) =>
  request.get<OuGplinks>(`/gpo/ous/${dnB64}/gplinks`, { params: { domain_id: domainId } })
export const setOuGplinks = (dnB64: string, domainId: number, payload: SetGplinksPayload) =>
  request.post<OuGplinks>(`/gpo/ous/${dnB64}/gplinks`, payload, { params: { domain_id: domainId } })
