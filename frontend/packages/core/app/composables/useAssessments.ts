/**
 * Typed API client composable for assessment endpoints.
 * Provides methods to list, take, and submit assessments.
 */

export interface Assessment {
  id: number
  title: string
  description: string
  module: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  questionCount: number
  passingScore: number
  timeLimitMinutes: number | null
  isPublished: boolean
  createdAt: string
}

export interface Question {
  id: number
  assessmentId: number
  text: string
  type: 'multiple_choice' | 'true_false'
  options: QuestionOption[]
  order: number
  explanation: string | null
}

export interface QuestionOption {
  id: string
  text: string
  isCorrect?: boolean
}

export interface AssessmentDetail extends Assessment {
  questions: Question[]
}

export interface AssessmentSubmission {
  assessmentId: number
  answers: AnswerEntry[]
  timeTakenSeconds: number
}

export interface AnswerEntry {
  questionId: number
  selectedOptionId: string
}

export interface AssessmentResult {
  id: number
  assessmentId: number
  assessmentTitle: string
  module: string
  score: number
  maxScore: number
  passingScore: number
  passed: boolean
  completedAt: string
  timeTakenSeconds: number
  questionsCorrect: number
  questionsTotal: number
  answers: ResultAnswer[]
}

export interface ResultAnswer {
  questionId: number
  questionText: string
  selectedOptionId: string
  selectedOptionText: string
  correctOptionId: string
  correctOptionText: string
  isCorrect: boolean
  explanation: string | null
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  hasMore: boolean
}

export function useAssessments() {
  const api = useApi()

  async function listAssessments(moduleId?: string): Promise<Assessment[]> {
    const params = moduleId ? `?module=${encodeURIComponent(moduleId)}` : ''
    return api.get<Assessment[]>(`/api/v1/assessments${params}`)
  }

  async function getAssessment(id: number): Promise<AssessmentDetail> {
    return api.get<AssessmentDetail>(`/api/v1/assessments/${id}`)
  }

  async function submitAssessment(
    id: number,
    submission: AssessmentSubmission,
  ): Promise<AssessmentResult> {
    return api.post<AssessmentResult>(
      `/api/v1/assessments/${id}/submit`,
      submission,
    )
  }

  async function getMyResults(
    limit = 10,
    offset = 0,
  ): Promise<PaginatedResponse<AssessmentResult>> {
    return api.get<PaginatedResponse<AssessmentResult>>(
      `/api/v1/assessments/me/results?limit=${limit}&offset=${offset}`,
    )
  }

  return {
    listAssessments,
    getAssessment,
    submitAssessment,
    getMyResults,
  }
}
