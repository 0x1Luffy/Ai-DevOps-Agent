import clsx from 'clsx'
import { CheckCircle, XCircle, Clock } from 'lucide-react'
import type { FixStep, FixExecution } from '../../types'
import { CopyButton } from '../shared/CopyButton'

interface FixStepsViewerProps {
  steps: FixStep[]
  executions?: FixExecution[]
}

function getStepResult(executions: FixExecution[] | undefined, idx: number) {
  if (!executions || idx >= executions.length) return null
  return executions[idx]?.result ?? null
}

export function FixStepsViewer({ steps, executions }: FixStepsViewerProps) {
  if (!steps.length) {
    return <p className="text-gray-500 text-sm italic">No fix steps available.</p>
  }

  return (
    <div className="space-y-3">
      {steps.map((step, idx) => {
        const result = getStepResult(executions, idx)

        return (
          <div
            key={idx}
            className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-4"
          >
            <div className="flex items-start gap-3 mb-3">
              <span className="w-6 h-6 rounded-full bg-indigo-600/30 text-indigo-400 text-xs flex items-center justify-center font-mono shrink-0 mt-0.5">
                {idx + 1}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <span className="text-gray-200 text-sm font-medium">{step.action}</span>
                  {result !== null && (
                    <span
                      className={clsx(
                        'flex items-center gap-1 text-xs font-medium',
                        result === 'success' && 'text-green-400',
                        result === 'failed' && 'text-red-400',
                        result === 'partial' && 'text-yellow-400',
                        result === 'skipped' && 'text-gray-500',
                      )}
                    >
                      {result === 'success' && <CheckCircle size={12} />}
                      {result === 'failed' && <XCircle size={12} />}
                      {(result === 'partial' || result === 'skipped') && <Clock size={12} />}
                      {result}
                    </span>
                  )}
                </div>
                <p className="text-gray-500 text-xs">{step.description}</p>
              </div>
            </div>

            {step.kubectlEquivalent && (
              <div className="flex items-center justify-between bg-gray-950 rounded px-3 py-2">
                <code className="text-green-400 text-xs font-mono flex-1 overflow-x-auto">
                  {step.kubectlEquivalent}
                </code>
                <CopyButton text={step.kubectlEquivalent} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
