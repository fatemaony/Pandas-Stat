import { ReturnButton } from "@/components/return-button"
import { SignInForm } from "@/components/auth-ui/sign-in-form"
import { SignInOauthButton } from "@/components/auth-ui/sign-in-oauth-button"
import Link from "next/link"
function Page() {
  return (
    <div className="mx-auto h-svh w-full mt-10">
      <ReturnButton href="/" label="Back to Home" />
      <div className="max-w-md mx-auto bg-gray-100 p-10 rounded-md shadow-sm">
        <h1 className="text-5xl font-bold text-center mb-10">Sign In</h1>
        <SignInForm />
        <p className="text-center text-gray-500 mt-4">Don't have an account? <Link className="text-blue-500 hover:underline" href="/auth/register">Register</Link></p>

        <hr className="max-w-sm" />

        <div className="flex max-w-sm gap-3 pt-5">
          <SignInOauthButton provider="google" />
          <SignInOauthButton provider="github" />
        </div>
      </div>

    </div>
  )
}
export default Page