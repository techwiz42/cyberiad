'use client'

import { useEffect, useState } from 'react'
import { Thread } from '@/types'
import { threadService } from '@/services/threads'
import Link from 'next/link'

export function ThreadList() {
 const [threads, setThreads] = useState<Thread[]>([])
 const [isLoading, setIsLoading] = useState(true)
 const [error, setError] = useState<string | null>(null)

 useEffect(() => {
   const fetchThreads = async () => {
     try {
       // TODO: Get token from auth context/store
       const token = 'your-auth-token'
       const response = await threadService.getThreads(token)
       setThreads(response.items)
       setIsLoading(false)
     } catch (err) {
       setError(err instanceof Error ? err.message : 'Failed to load threads')
       setIsLoading(false)
     }
   }

   fetchThreads()
 }, [])

 if (isLoading) {
   return (
     <div className="flex justify-center items-center h-64">
       <div className="text-gray-500">Loading threads...</div>
     </div>
   )
 }

 if (error) {
   return (
     <div className="bg-red-50 border border-red-200 rounded-md p-4">
       <div className="text-red-700">{error}</div>
     </div>
   )
 }

 return (
   <div className="space-y-4">
     {threads.map((thread) => (
       <Link 
         key={thread.id} 
         href={`/thread/${thread.id}`}
         className="block"
       >
         <div className="bg-white shadow rounded-lg p-6 hover:shadow-md transition-shadow">
           <h2 className="text-xl font-semibold text-gray-900">
             {thread.title}
           </h2>
           {thread.description && (
             <p className="mt-2 text-gray-600">
               {thread.description}
             </p>
           )}
           <div className="mt-4 flex items-center space-x-4 text-sm text-gray-500">
             <div>
               {thread.participants.length} participant{thread.participants.length !== 1 ? 's' : ''}
             </div>
             <div>•</div>
             <div>
               {thread.agents.filter(a => a.isActive).length} active agent{thread.agents.filter(a => a.isActive).length !== 1 ? 's' : ''}
             </div>
             <div>•</div>
             <div>
               Last active: {new Date(thread.lastActivityAt).toLocaleDateString()}
             </div>
           </div>
         </div>
       </Link>
     ))}
   </div>
 )
}
