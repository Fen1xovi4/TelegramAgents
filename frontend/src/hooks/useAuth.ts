import { useQuery } from '@tanstack/react-query'
import { getMe, User } from '../api/auth'

export function useAuth() {
  const token = localStorage.getItem('access_token')

  const { data: user, isLoading, error } = useQuery<User>({
    queryKey: ['auth', 'me'],
    queryFn: getMe,
    enabled: !!token,
    retry: false,
  })

  return {
    user,
    isLoading,
    isAuthenticated: !!user,
    error,
  }
}
