// src/app/page.tsx
import { ThreadList } from '@/components/thread/ThreadList'

export default function Home() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">
          Discussion Threads
        </h2>
        <button className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-md">
          New Thread
        </button>
      </div>
      <ThreadList />
    </div>
  )
}
