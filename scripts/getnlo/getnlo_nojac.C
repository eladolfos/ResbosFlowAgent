// getnlo_nojac.C -- Yao's NLO qT integrator for E605 (Q^3 dsigma/dQ/dy, measured in y: no dy/dxF Jacobian). Same as getnlo.C except the Jacobian factor
// ECM/(2 sqrt(Q^2+qT^2) cosh y) is absent. From ~/InstallSources/YaoRepro/getnlo_nojac.C (Yao's getnlo.cpp with standard includes and ECM as argument); see getnlo.C.
#include <vector>
#include <fstream>
#include <sstream>
#include <iostream>
#include <cmath>
#include "TGraph.h"
#include "TSpline.h"
#include "TFile.h"
#include "TString.h"
using namespace std;


void getnlo_nojac(double ECM = 38.75)
{
 double Q, Y;
 double m_ECM = ECM;
 double OnlyPert = 0.0;

 auto Simpson = [&](const size_t& nx, const double& dx, const std::vector<double>& f, double& err) {
    double simp, errd, trpz;
    size_t ms = 0;
    if(dx <= 0) return 0.0;
    if(nx <= 1) simp = 0;
    else if(nx == 2) {
        simp = (f[0]+f[1])/2.0;
        errd = (f[0]-f[1])/2.0;
    } else {
        ms = nx % 2;

        double add = 0;
        size_t nz = nx;
        if(ms == 0) {
            add = (9.0*f[nx-1]+19.0*f[nx-2]-5*f[nx-3]+f[nx-4])/24.0;
            nz--;
        }

        if(nz == 3) {
            simp = (f[0]+4*f[1]+f[2])/3.0;
            trpz = (f[0]+2*f[1]+f[2])/2.0;
        } else {
            double se = f[1];
            double s0 = 0;
            size_t nm1 = nz - 1;
            for(size_t i = 3; i < nm1; i += 2) {
                se += f[i];
                s0 += f[i-1];
            }
            simp = (f[0]+4*se+2*s0+f[nz-1])/3.0;
            trpz = (f[0]+2*se+2*s0+f[nz-1])/2.0;
        }

        errd = trpz - simp;
        simp = simp + add;
    }

    if(fabs(simp) > 1E-10) err = errd/simp;
    else err = 0.0;

    simp *= dx;

    return simp;
 };

 auto interpolation = [&](vector<double> X, vector<double> Y){
   TGraph* g = new TGraph(X.size());
   for(int i = 0; i < X.size(); i++){
     g->SetPointX(i, X.at(i));
     g->SetPointY(i, Y.at(i));
   }
   TSpline3* spline = new TSpline3("s", g);
   return spline;
 };

 auto integration = [&](TSpline3* spline_pert, TSpline3* spline_delsig, double pTSep){
   double pTmin = pTSep;
   double pTmax = 10.0;
   size_t pTrange = 1000;
   double dpT = (pTmax - pTmin) / (pTrange - 1);
   double err;

   double log_pTmin = log(pTmin);
   double log_pTmax = log(pTmax);
   double log_dpT = (log_pTmax - log_pTmin) / (pTrange - 1);

   vector<double> pert(pTrange);
   vector<double> delsig(pTrange);
   vector<double> nlo(pTrange);
   for(int i = 0; i < pTrange; i++){
     double log_pT = log_pTmin + i*log_dpT;
     double pT = exp(log_pT);

     pert.at(i) = spline_pert->Eval(pT) * pT;

     nlo.at(i) = pert.at(i);

     nlo.at(i) *= pow(Q, 3) / 1000.0 * 2.0 * Q ;
     //cout<<pT<<"  "<<spline_asy->Eval(pT)<<"  "<<spline_delsig->Eval(pT)<<"  "<<Q<<"  "<<Y<<"  "<<m_ECM<<endl;
   }

   double result = Simpson(pTrange, log_dpT, nlo, err);
   OnlyPert = result;
   result += spline_delsig->Eval(pTSep) * pow(Q, 3) / 1000.0 * 2.0 * Q ;

   return result;
 };

 auto ReadTable = [&](TString FileName, int iColumn){
    ifstream datafile(FileName);

    string FileLine;
    vector<double> result;

    vector<vector<double>> FullTable;
    while(getline(datafile, FileLine)){
      vector<double> LineVector;
      double Value;
      stringstream LineStream(FileLine);
      while(LineStream >> Value){
        LineVector.push_back(Value);
      }
      if(LineVector.size() == 0) break;

      FullTable.push_back(LineVector);//FullTable.at(i).at(j) is i row and j column
    }

    for(int i = 0; i < FullTable.size(); i++){
      result.push_back(FullTable.at(i).at(iColumn));
    }

    return result;
 };

 auto ReadTable_y = [&](TString FileName, int iColumn, int iLine){
    ifstream datafile(FileName);

    string FileLine;
    vector<double> result;

    vector<vector<double>> FullTable;
    while(getline(datafile, FileLine)){
      vector<double> LineVector;
      double Value;
      stringstream LineStream(FileLine);
      while(LineStream >> Value){
        LineVector.push_back(Value);
      }
      if(LineVector.size() == 0) break;

      FullTable.push_back(LineVector);//FullTable.at(i).at(j) is i row and j column
    }

    for(int i = 0; i < FullTable.size(); i++){
      if(i % 3 != iLine) continue;
      result.push_back(FullTable.at(i).at(iColumn));
    }

    return result;
 };

 vector<double> pT_pert = ReadTable_y("nlo_y.log", 1, 0);
 vector<double> val_pert = ReadTable_y("nlo_y.log", 2, 1);
 vector<double> pT_asy = ReadTable("nlo_asy.log", 1);
 vector<double> val_asy = ReadTable("nlo_asy.log", 3);
 vector<double> pT_delsig = ReadTable("nlo_delsig.log", 1);
 vector<double> val_delsig = ReadTable("nlo_delsig.log", 3);
 vector<double> Qs = ReadTable("nlo_asy.log", 0);
 vector<double> Ys = ReadTable("nlo_asy.log", 2);

 TFile* file = new TFile("file_nlo.root", "RECREATE");
 file->cd();
 TGraph* graph_pert = new TGraph(val_pert.size());
 for(int i = 0; i < val_pert.size(); i++){
   graph_pert->SetPointX(i, pT_pert.at(i));
   graph_pert->SetPointY(i, val_pert.at(i));
 }

 TGraph* graph_delsig = new TGraph(val_delsig.size());
 for(int i = 0; i < val_delsig.size(); i++){
   graph_delsig->SetPointX(i, pT_delsig.at(i));
   graph_delsig->SetPointY(i, val_delsig.at(i));
 }

 graph_pert->Write("pert");
 graph_delsig->Write("delsig");
 file->Close();

 Q = Qs.at(0);
 Y = Ys.at(0);

 TSpline3* spline_pert = interpolation(pT_pert, val_pert);
 TSpline3* spline_delsig = interpolation(pT_delsig, val_delsig);

 vector<double> v_Pert;
 vector<double> v_Result;

 double result;
 result = integration(spline_pert, spline_delsig, 0.01);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.02);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.03);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.04);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.05);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.06);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.07);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.08);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.09);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 result = integration(spline_pert, spline_delsig, 0.1);
 v_Pert.push_back(OnlyPert);
 v_Result.push_back(result);
 cout<<OnlyPert<<"  "<<result<<endl;

 cout<<"np.array([";
 for(int i = 0; i < v_Pert.size(); i++){
   cout<<v_Pert.at(i);
   if(i != v_Pert.size() - 1) cout<<", ";
   else cout<<"])"<<endl;
 }

 cout<<"np.array([";
 for(int i = 0; i < v_Result.size(); i++){
   cout<<v_Result.at(i);
   if(i != v_Result.size() - 1) cout<<", ";
   else cout<<"])"<<endl;
 }

}
