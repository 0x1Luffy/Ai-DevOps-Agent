import clsx from 'clsx'
import { formatDistanceToNow } from 'date-fns'
import { GitBranch, TrendingUp, TrendingDown } from 'lucide-react'
import type { PipelineHealth } from '../../types'
import { FailureClassificationBadge } from './FailureClassificationBadge'
import type { JenkinsFailureType } from '../../types'

interface PipelineCardProps {
  pipeline: PipelineHealth
}

export function PipelineCard({ pipeline }: PipelineCardProps) {
  const rate = pipeline.successRate
  const isGood = rate >= 80

  return (
    <div className="bg-gray-800/60 border border-gray-700/60 rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/15 flex items-center justify-center shrink-0">
            <GitBranch size={14} className="text-indigo-400" />
          </div>
          <div className="min-w-0">
            <p className="text-gray-200 text-sm font-medium truncate">{pipeline.name}</p>
            {pipeline.lastBuild && (
              <p className="text-gray-600 text-xs">
                {formatDistanceToNow(new Date(pipeline.lastBuild), { addSuffix: true })}
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end shrink-0">
          <div className="flex items-center gap-1">
            {isGood ? (
              <TrendingUp size={12} className="text-green-400" />
            ) : (
              <TrendingDown size={12} className="text-red-400" />
            )}
            <span
              className={clsx(
                'text-sm font-semibold tabular-nums',
                isGood ? 'text-green-400' : 'text-red-400',
              )}
            >
              {rate.toFixed(1)}%
            </span>
          </div>
          <span className="text-gray-600 text-xs">{pipeline.totalBuilds} builds</span>
        </div>
      </div>

      {/* Success rate bar */}
      <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={clsx(
            'h-full rounded-full transition-all duration-500',
            rate >= 80 ? 'bg-green-500' : rate >= 60 ? 'bg-yellow-500' : 'bg-red-500',
          )}
          style={{ width: `${rate}%` }}
        />
      </div>

      <div className="flex items-center justify-between">
        {pipeline.commonFailureType && (
          <FailureClassificationBadge failureType={pipeline.commonFailureType as JenkinsFailureType} />
        )}
        {pipeline.avgDurationSeconds !== null && (
          <span className="text-gray-600 text-xs tabular-nums ml-auto">
            avg {Math.round(pipeline.avgDurationSeconds)}s
          </span>
        )}
      </div>
    </div>
  )
}
